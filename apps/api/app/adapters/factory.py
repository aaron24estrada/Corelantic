"""Select provider implementations from settings.

Application code depends on the ``DataSource`` and ``LLMProvider`` interfaces; this is
the one place that names a concrete implementation. Adapters that are not yet built
raise ``ProviderNotConfiguredError``, which the API surfaces as a clear 503 rather than a
crash — the honest state until the external dependency is provisioned.
"""

import threading

from app.adapters.data.base import DataSource
from app.adapters.data.fixture import FixtureDataSource
from app.adapters.llm.base import LLMProvider
from app.core.config import Settings


class ProviderNotConfiguredError(Exception):
    """A selected provider cannot be built yet (missing implementation or credentials)."""


_fixture_lock = threading.Lock()
_fixture: FixtureDataSource | None = None

_azure_lock = threading.Lock()
_azure: DataSource | None = None


def _fixture_data_source() -> FixtureDataSource:
    # Seed exactly once per process (double-checked lock — concurrent cold-start requests
    # would otherwise each pay the seed cost); the in-memory engine then holds the data.
    global _fixture
    if _fixture is None:
        with _fixture_lock:
            if _fixture is None:
                _fixture = FixtureDataSource()
    return _fixture


def _azure_sql_data_source(settings: Settings) -> DataSource:
    # One engine/pool per process; the vendor SDK stays behind this lazy import.
    global _azure
    if _azure is None:
        with _azure_lock:
            if _azure is None:
                from app.adapters.data.azure_sql import AzureSqlDataSource

                _azure = AzureSqlDataSource(settings)
    return _azure


def build_data_source(settings: Settings) -> DataSource:
    if settings.data_source == "fixture":
        return _fixture_data_source()
    if settings.data_source == "azure_sql":
        _require_azure_sql_config(settings)
        return _azure_sql_data_source(settings)
    raise ProviderNotConfiguredError(f"Unknown data source: {settings.data_source!r}.")


def _require_azure_sql_config(settings: Settings) -> None:
    if not settings.azure_sql_server or not settings.azure_sql_database:
        raise ProviderNotConfiguredError(
            "Azure SQL requires CORELANTIC_API_AZURE_SQL_SERVER and _AZURE_SQL_DATABASE."
        )
    mode = settings.azure_sql_auth_mode
    if mode == "service_principal" and not (
        settings.azure_sql_tenant_id
        and settings.azure_sql_client_id
        and settings.azure_sql_client_secret
    ):
        raise ProviderNotConfiguredError(
            "service_principal auth requires tenant id, client id, and client secret."
        )
    if mode not in ("device_code", "service_principal"):
        raise ProviderNotConfiguredError(f"Unknown azure_sql_auth_mode: {mode!r}.")


def build_llm(settings: Settings) -> LLMProvider:
    if settings.llm_provider == "claude":
        raise ProviderNotConfiguredError(
            "Claude LLM provider is not wired yet (pending CORELANTIC_API_ANTHROPIC_API_KEY)."
        )
    raise ProviderNotConfiguredError(f"Unknown LLM provider: {settings.llm_provider!r}.")
