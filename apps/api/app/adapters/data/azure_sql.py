"""Read-only Azure SQL ``DataSource`` over the KRW warehouse.

Confines the pyodbc + azure-identity vendor SDKs to this adapter. Auth is Entra ID, not a SQL
login: one bearer token is acquired, cached until shortly before it expires, and handed to ODBC
on each physical connect. The compiled ``Select`` is dialect-neutral; importing the mssql
rendering (side effect) lets it run unchanged. pyodbc blocks, so reads run on a worker thread to
honour the async contract.
"""

import asyncio
import logging
import struct
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from azure.core.credentials import TokenCredential
from azure.identity import (
    AuthenticationRecord,
    AuthenticationRequiredError,
    ClientSecretCredential,
    DeviceCodeCredential,
    TokenCachePersistenceOptions,
)
from sqlalchemy import Select, create_engine, event
from sqlalchemy.engine import URL, Engine

import app.adapters.data.mssql  # noqa: F401 — registers the DateBucket mssql rendering
from app.core.config import Settings
from app.query.rows import Row

logger = logging.getLogger("corelantic.azure_sql")

_SQL_COPT_SS_ACCESS_TOKEN = 1256  # ODBC attribute id for an AAD bearer token
_TOKEN_SCOPE = "https://database.windows.net/.default"
_QUERY_TIMEOUT_SECONDS = 60
_TOKEN_REFRESH_MARGIN_SECONDS = 60
_POOL_RECYCLE_SECONDS = 1800  # comfortably under the Entra token lifetime

# The token cache (OS keychain) holds the refresh token; this records which account owns it,
# which is what lets a fresh process find it instead of prompting again. Holds no secret.
_AUTH_RECORD_PATH = Path.home() / ".corelantic" / "krw-auth-record.json"


class AzureSqlDataSource:
    def __init__(self, settings: Settings) -> None:
        self._auth_record = _load_auth_record()
        self._credential = build_credential(settings, self._auth_record)
        self._token_lock = threading.Lock()
        self._token: bytes | None = None
        self._token_expires_at = 0.0
        self._engine = create_engine(
            connection_url(settings), pool_pre_ping=True, pool_recycle=_POOL_RECYCLE_SECONDS
        )

        @event.listens_for(self._engine, "do_connect")
        def _inject_token(_dialect: Any, _record: Any, _cargs: Any, cparams: Any) -> None:
            cparams["attrs_before"] = {_SQL_COPT_SS_ACCESS_TOKEN: self._access_token()}

        @event.listens_for(self._engine, "connect")
        def _cap_query_time(dbapi_connection: Any, _record: Any) -> None:
            dbapi_connection.timeout = _QUERY_TIMEOUT_SECONDS

        self.sign_in()

    def sign_in(self) -> None:
        """Authenticate now, so any interactive prompt happens at startup rather than mid-request.

        The interactive credential is built with automatic authentication disabled, so a token
        that cannot be served from the cache raises instead of silently opening a device-code
        flow. That makes the two cases explicit: reuse the cached login and stay quiet, or prompt
        once here and record the account that answered — including when an old record has gone
        stale, which is why the record is rewritten on every interactive sign-in.
        """
        try:
            self._access_token()
            return
        except AuthenticationRequiredError:
            if not isinstance(self._credential, DeviceCodeCredential):
                raise

        self._auth_record = self._credential.authenticate(scopes=[_TOKEN_SCOPE])
        _save_auth_record(self._auth_record)
        self._access_token()

    def _access_token(self) -> bytes:
        # Serialised: the pool opens several connections at once, and an unsynchronised fetch
        # would start a separate interactive login for each one.
        if self._token is not None and time.time() < self._token_expires_at:
            return self._token
        with self._token_lock:
            if self._token is not None and time.time() < self._token_expires_at:
                return self._token
            token = self._credential.get_token(_TOKEN_SCOPE)
            self._token = _packed_token(token.token)
            self._token_expires_at = float(token.expires_on) - _TOKEN_REFRESH_MARGIN_SECONDS
            return self._token

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


def build_credential(
    settings: Settings, auth_record: AuthenticationRecord | None = None
) -> TokenCredential:
    if settings.azure_sql_auth_mode == "service_principal":
        # Explicit client credentials, not DefaultAzureCredential, whose fallbacks are too broad.
        secret = settings.azure_sql_client_secret
        return ClientSecretCredential(
            tenant_id=str(settings.azure_sql_tenant_id),
            client_id=str(settings.azure_sql_client_id),
            client_secret=secret.get_secret_value() if secret else "",
        )
    return DeviceCodeCredential(
        tenant_id=settings.azure_sql_tenant_id or "organizations",
        cache_persistence_options=TokenCachePersistenceOptions(name="corelantic-krw"),
        authentication_record=auth_record,
        # Raise rather than prompt when the cache cannot answer: sign-in is a startup decision,
        # never something that opens a device-code flow inside a request nobody is watching.
        disable_automatic_authentication=True,
        prompt_callback=_show_device_code,
    )


def _show_device_code(verification_uri: str, user_code: str, expires_on: datetime) -> None:
    # Printed rather than logged: the JSON formatter would fold the one message a developer has
    # to act on into a dense line among the SDK's own output.
    print(
        "\n"
        "  ┌──────────────────────────────────────────────────────────┐\n"
        "  │  AZURE SQL SIGN-IN REQUIRED                              │\n"
        "  └──────────────────────────────────────────────────────────┘\n"
        f"     1.  Open   {verification_uri}\n"
        f"     2.  Code   {user_code}\n"
        f"     3.  Sign in with your KRW account   (code expires {expires_on:%H:%M} UTC)\n",
        flush=True,
    )


def _load_auth_record() -> AuthenticationRecord | None:
    try:
        return AuthenticationRecord.deserialize(_AUTH_RECORD_PATH.read_text())
    except (OSError, ValueError):
        return None


def _save_auth_record(record: AuthenticationRecord) -> None:
    try:
        _AUTH_RECORD_PATH.parent.mkdir(parents=True, exist_ok=True)
        _AUTH_RECORD_PATH.write_text(record.serialize())
    except OSError:
        # One extra prompt next start is the whole cost of failing here.
        logger.debug("could not persist the Entra authentication record", exc_info=True)


def _packed_token(token: str) -> bytes:
    # pyodbc wants a length-prefixed UTF-16LE buffer.
    raw = token.encode("utf-16-le")
    return struct.pack("<i", len(raw)) + raw


def token_struct(credential: TokenCredential) -> bytes:
    return _packed_token(credential.get_token(_TOKEN_SCOPE).token)
