import struct
from typing import Any

import pytest
from azure.core.credentials import AccessToken
from azure.identity import ClientSecretCredential, DeviceCodeCredential
from sqlalchemy import column, select
from sqlalchemy.dialects.mssql.base import MSDialect

from app.adapters.data.azure_sql import build_credential, connection_url, token_struct
from app.adapters.factory import ProviderNotConfiguredError, build_data_source
from app.core.config import Settings
from app.query.time import DateBucket, Grain


def _mssql(grain: Grain) -> str:
    statement = select(DateBucket(grain, column("d")).label("period"))
    dialect = MSDialect()  # type: ignore[no-untyped-call]  # SQLAlchemy dialect ctor is untyped
    return " ".join(statement.compile(dialect=dialect).string.split())


def test_date_bucket_renders_sql_server_truncation_per_grain() -> None:
    # Shift back a day so Sunday buckets with the preceding Monday (DATEDIFF uses Sundays).
    assert "DATEADD(week, DATEDIFF(week, 0, DATEADD(day, -1, d)), 0)" in _mssql(Grain.WEEK)
    assert "DATEADD(month, DATEDIFF(month, 0, d), 0)" in _mssql(Grain.MONTH)
    assert "CAST(d AS date)" in _mssql(Grain.DAY)


class _StubCredential:
    def get_token(self, *scopes: str, **kwargs: Any) -> AccessToken:
        return AccessToken("tok", 0)


def test_token_struct_is_length_prefixed_utf16le() -> None:
    packed = token_struct(_StubCredential())
    body = "tok".encode("utf-16-le")
    assert packed == struct.pack("<i", len(body)) + body
    assert struct.unpack("<i", packed[:4])[0] == len(packed) - 4


def _settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "azure_sql_server": "krw-platform-sql.database.windows.net",
        "azure_sql_database": "krw-platform",
    }
    return Settings(**{**base, **overrides})  # type: ignore[arg-type]


def test_connection_url_targets_the_server_encrypted() -> None:
    odbc = connection_url(_settings()).query["odbc_connect"]
    assert "Driver={ODBC Driver 18 for SQL Server}" in odbc
    assert "Server=tcp:krw-platform-sql.database.windows.net,1433" in odbc
    assert "Database=krw-platform" in odbc
    assert "Encrypt=yes" in odbc and "TrustServerCertificate=no" in odbc


def test_build_credential_picks_the_mode() -> None:
    device = build_credential(_settings(azure_sql_auth_mode="device_code"))
    assert isinstance(device, DeviceCodeCredential)
    sp = build_credential(
        _settings(
            azure_sql_auth_mode="service_principal",
            azure_sql_tenant_id="t",
            azure_sql_client_id="c",
            azure_sql_client_secret="s",
        )
    )
    assert isinstance(sp, ClientSecretCredential)


def test_factory_requires_server_and_database() -> None:
    with pytest.raises(ProviderNotConfiguredError):
        build_data_source(Settings(data_source="azure_sql"))


def test_factory_service_principal_requires_credentials() -> None:
    settings = _settings(data_source="azure_sql", azure_sql_auth_mode="service_principal")
    with pytest.raises(ProviderNotConfiguredError):
        build_data_source(settings)


def test_factory_rejects_unknown_auth_mode() -> None:
    with pytest.raises(ProviderNotConfiguredError):
        build_data_source(_settings(data_source="azure_sql", azure_sql_auth_mode="whoami"))
