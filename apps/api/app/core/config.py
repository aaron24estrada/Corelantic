"""Application settings, loaded from the environment.

All variables use the ``CORELANTIC_API_`` prefix, e.g. ``CORELANTIC_API_PORT=8080``.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# apps/api, the directory that holds this package and the semantic registry.
PACKAGE_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CORELANTIC_API_", env_file=".env", extra="ignore")

    host: str = "127.0.0.1"
    port: int = 8080

    # The web app is the only permitted caller. In production the API is reachable, so
    # the network is not a trust boundary: the web BFF presents this shared secret on
    # every request. None disables the check (local dev only).
    internal_api_key: str | None = None

    # Allowed browser origin, for CORS if the web app ever needs a direct call.
    web_origin: str = "http://localhost:3000"

    # Provider selection (config-selected, swappable — see standards/fastapi.md).
    data_source: str = "azure_sql"
    llm_provider: str = "claude"

    # Read-only connection to the source database. None until provisioned (docs O-1).
    database_url: str | None = None
    # Credentials for the LLM provider. None until provisioned.
    anthropic_api_key: str | None = None

    # Directory holding the semantic registry (metric and dimension definitions).
    semantic_dir: Path = PACKAGE_ROOT / "semantic"


@lru_cache
def get_settings() -> Settings:
    """Return the settings singleton."""
    return Settings()
