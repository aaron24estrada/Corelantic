"""Select provider implementations from settings.

Application code depends on the ``DataSource`` and ``LLMProvider`` interfaces; this is
the one place that names a concrete implementation. Adapters that are not yet built
raise ``ProviderNotConfiguredError``, which the API surfaces as a clear 503 rather than a
crash — the honest state until the external dependency is provisioned.
"""

from app.adapters.data.base import DataSource
from app.adapters.llm.base import LLMProvider
from app.core.config import Settings


class ProviderNotConfiguredError(Exception):
    """A selected provider cannot be built yet (missing implementation or credentials)."""


def build_data_source(settings: Settings) -> DataSource:
    if settings.data_source == "azure_sql":
        raise ProviderNotConfiguredError(
            "Azure SQL data source is not implemented yet "
            "(pending docs O-1: confirmed edition and a read-only credential)."
        )
    raise ProviderNotConfiguredError(f"Unknown data source: {settings.data_source!r}.")


def build_llm(settings: Settings) -> LLMProvider:
    if settings.llm_provider == "claude":
        raise ProviderNotConfiguredError(
            "Claude LLM provider is not wired yet (pending CORELANTIC_API_ANTHROPIC_API_KEY)."
        )
    raise ProviderNotConfiguredError(f"Unknown LLM provider: {settings.llm_provider!r}.")
