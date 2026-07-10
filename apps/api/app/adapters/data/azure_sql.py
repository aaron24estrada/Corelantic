"""Read-only Azure SQL ``DataSource`` over the KRW warehouse.

Confines the pyodbc + azure-identity vendor SDKs to this adapter. Auth is Entra ID, not a
SQL login: a bearer token is fetched per physical connection and handed to ODBC. The
compiled ``Select`` is dialect-neutral; importing the mssql rendering (side effect) lets it
run unchanged. pyodbc blocks, so reads run on a worker thread to honour the async contract.
"""

import asyncio
import struct
from typing import Any

from azure.core.credentials import TokenCredential
from azure.identity import ClientSecretCredential, DeviceCodeCredential
from sqlalchemy import Select, create_engine, event
from sqlalchemy.engine import URL, Engine

import app.adapters.data.mssql  # noqa: F401 — registers the DateBucket mssql rendering
from app.core.config import Settings
from app.query.rows import Row

# ODBC attribute for an AAD access token, and the SQL scope it must be issued for.
_SQL_COPT_SS_ACCESS_TOKEN = 1256
_TOKEN_SCOPE = "https://database.windows.net/.default"
_QUERY_TIMEOUT_SECONDS = 60


class AzureSqlDataSource:
    def __init__(self, settings: Settings) -> None:
        self._credential = build_credential(settings)
        # pool_recycle keeps connections well under the Entra token lifetime.
        self._engine = create_engine(
            connection_url(settings), pool_pre_ping=True, pool_recycle=1800
        )

        @event.listens_for(self._engine, "do_connect")
        def _inject_token(_dialect: Any, _record: Any, _cargs: Any, cparams: Any) -> None:
            # Fresh per connect; the credential caches and refreshes the token itself.
            cparams["attrs_before"] = {_SQL_COPT_SS_ACCESS_TOKEN: token_struct(self._credential)}

        @event.listens_for(self._engine, "connect")
        def _cap_query_time(dbapi_connection: Any, _record: Any) -> None:
            # A slow read must not pin a pool slot and worker thread indefinitely.
            dbapi_connection.timeout = _QUERY_TIMEOUT_SECONDS

    async def run(self, statement: Select[Any]) -> list[Row]:
        return await asyncio.to_thread(self._run, statement)

    def _run(self, statement: Select[Any]) -> list[Row]:
        with self._engine.connect() as connection:
            return [dict(row) for row in connection.execute(statement).mappings().all()]

    @property
    def engine(self) -> Engine:
        return self._engine


def connection_url(settings: Settings) -> URL:
    odbc = (
        f"Driver={{{settings.azure_sql_odbc_driver}}};"
        f"Server=tcp:{settings.azure_sql_server},1433;"
        f"Database={settings.azure_sql_database};"
        "Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"
    )
    return URL.create("mssql+pyodbc", query={"odbc_connect": odbc})


def build_credential(settings: Settings) -> TokenCredential:
    if settings.azure_sql_auth_mode == "service_principal":
        # Explicit client-credentials for headless/prod — not DefaultAzureCredential, whose
        # fallbacks are too broad. The factory verifies these are set; secret never logged.
        secret = settings.azure_sql_client_secret
        return ClientSecretCredential(
            tenant_id=str(settings.azure_sql_tenant_id),
            client_id=str(settings.azure_sql_client_id),
            client_secret=secret.get_secret_value() if secret else "",
        )
    return DeviceCodeCredential(tenant_id=settings.azure_sql_tenant_id or "organizations")


def token_struct(credential: TokenCredential) -> bytes:
    # pyodbc wants the token as a length-prefixed UTF-16LE buffer.
    raw = credential.get_token(_TOKEN_SCOPE).token.encode("utf-16-le")
    return struct.pack("<i", len(raw)) + raw
