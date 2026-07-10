"""The data-source seam.

All source-data reads go through this interface with a read-only, least-privilege
account. Concrete adapters (Azure SQL, pending docs O-1) live beside this module and are
selected by the factory. Application code depends only on this Protocol.
"""

from typing import Any, Protocol

from sqlalchemy import Select

from app.query.rows import Row


class DataSource(Protocol):
    async def run(self, statement: Select[Any]) -> list[Row]:
        """Execute a read-only SELECT statement (values bound in it) and return rows.

        Driver types do not escape this package: every cell is a ``CellValue``.
        """
        ...
