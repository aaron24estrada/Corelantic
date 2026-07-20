"""Read-only Azure SQL ``DataSource`` over the KRW warehouse.

Confines the pyodbc + azure-identity vendor SDKs to this adapter. Auth is Entra ID, not a
SQL login: a bearer token is fetched per physical connection and handed to ODBC. The
compiled ``Select`` is dialect-neutral; importing the mssql rendering (side effect) lets it
run unchanged. pyodbc blocks, so reads run on a worker thread to honour the async contract.
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

# ODBC attribute for an AAD access token, and the SQL scope it must be issued for.
_SQL_COPT_SS_ACCESS_TOKEN = 1256
_TOKEN_SCOPE = "https://database.windows.net/.default"
_QUERY_TIMEOUT_SECONDS = 60


class AzureSqlDataSource:
    def __init__(self, settings: Settings) -> None:
        self._credential = build_credential(settings)
        self._token_lock = threading.Lock()
        self._token: bytes | None = None
        self._token_expires_at = 0.0
        # pool_recycle keeps connections well under the Entra token lifetime.
        self._engine = create_engine(
            connection_url(settings), pool_pre_ping=True, pool_recycle=1800
        )

        @event.listens_for(self._engine, "do_connect")
        def _inject_token(_dialect: Any, _record: Any, _cargs: Any, cparams: Any) -> None:
            cparams["attrs_before"] = {_SQL_COPT_SS_ACCESS_TOKEN: self._access_token()}

        @event.listens_for(self._engine, "connect")
        def _cap_query_time(dbapi_connection: Any, _record: Any) -> None:
            # A slow read must not pin a pool slot and worker thread indefinitely.
            dbapi_connection.timeout = _QUERY_TIMEOUT_SECONDS

        # Sign in while the process is starting rather than during the first query. The dashboard
        # opens ~16 connections at once, so a lazy first auth raced sixteen ways: several device
        # codes printed at once, several logins demanded. Doing it here means the prompt appears
        # once, at a predictable moment, before anything can race it.
        self.sign_in()

    def sign_in(self) -> None:
        """Acquire the access token up front, prompting for a device-code login if needed.

        For the interactive credential this goes through ``authenticate`` so the resulting
        account can be remembered: silent when the cache still holds a refresh token for it,
        interactive (with the banner) when it does not.
        """
        if isinstance(self._credential, DeviceCodeCredential):
            _save_auth_record(self._credential.authenticate(scopes=[_TOKEN_SCOPE]))
        self._access_token()

    def _access_token(self) -> bytes:
        """One token, fetched once and shared by every connect.

        Each physical connection needs a bearer token, and the pool opens several at once. Without
        this lock every racing connect starts its own interactive flow. The first caller
        authenticates; the rest wait and reuse the same token until it nears expiry.
        """
        if self._token is not None and time.time() < self._token_expires_at:
            return self._token
        with self._token_lock:
            # Re-check inside the lock: whoever waited here is served by the first caller's token.
            if self._token is not None and time.time() < self._token_expires_at:
                return self._token
            token = self._credential.get_token(_TOKEN_SCOPE)
            self._token = _pack(token.token)
            # Refresh a minute early so a connect never races the expiry.
            self._token_expires_at = float(token.expires_on) - 60
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


# Which account last signed in. The token cache holds the refresh token (in the OS keychain);
# this says *whose* it is, which is what lets the credential find it silently in a new process.
# It carries no secret — account id, tenant, username — and lives outside the repo.
_AUTH_RECORD_PATH = Path.home() / ".corelantic" / "krw-auth-record.json"


def _load_auth_record() -> AuthenticationRecord | None:
    try:
        return AuthenticationRecord.deserialize(_AUTH_RECORD_PATH.read_text())
    except (OSError, ValueError):
        # No record, unreadable, or written by an older version: fall back to prompting.
        return None


def _save_auth_record(record: AuthenticationRecord) -> None:
    try:
        _AUTH_RECORD_PATH.parent.mkdir(parents=True, exist_ok=True)
        _AUTH_RECORD_PATH.write_text(record.serialize())
    except OSError:
        # Failing to remember the account costs one extra prompt next start, not a broken run.
        logger.debug("could not persist the Entra authentication record", exc_info=True)


def _device_code_prompt(verification_uri: str, user_code: str, expires_on: datetime) -> None:
    """Print the sign-in instructions where a developer will actually see them.

    Printed, not logged: this is the one message that must not be missed, and the JSON formatter
    would fold it into a single dense line among the SDK's own chatter (which `configure_logging`
    also quiets, for the same reason).
    """
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
    # Persist the token cache so a dev restart (and every hot-reload) reuses the last login
    # instead of re-prompting. Tokens live in the OS keychain (encrypted), not in the repo; the
    # refresh token keeps silent auth working for ~90 days. Prod uses the service principal above
    # and never reaches this branch.
    return DeviceCodeCredential(
        tenant_id=settings.azure_sql_tenant_id or "organizations",
        cache_persistence_options=TokenCachePersistenceOptions(name="corelantic-krw"),
        # The cache holds the refresh token; the record says which account owns it. With the
        # cache alone a fresh process has no account to match and prompts anyway — which is
        # exactly what "why am I logging in again?" looked like.
        authentication_record=_load_auth_record(),
        prompt_callback=_device_code_prompt,
    )


def _pack(token: str) -> bytes:
    # pyodbc wants the token as a length-prefixed UTF-16LE buffer.
    raw = token.encode("utf-16-le")
    return struct.pack("<i", len(raw)) + raw


def token_struct(credential: TokenCredential) -> bytes:
    return _pack(credential.get_token(_TOKEN_SCOPE).token)
