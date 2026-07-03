"""The data-source seam.

All source-data reads go through this interface with a read-only, least-privilege
account. Concrete adapters (Azure SQL, pending docs O-1) live beside this module and are
selected by the factory. Application code depends only on this Protocol.
"""

from collections.abc import Mapping
from typing import Protocol


class DataSource(Protocol):
    async def run(self, sql: str, params: Mapping[str, str]) -> list[dict[str, object]]:
        """Execute a read-only, parameterized query and return rows as dicts."""
        ...
