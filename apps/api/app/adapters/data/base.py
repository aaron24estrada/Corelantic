"""The data-source seam.

All source-data reads go through this interface with a read-only, least-privilege
account. Concrete adapters (Azure SQL, pending docs O-1) live beside this module and are
selected by the factory. Application code depends only on this Protocol.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Protocol

from sqlalchemy import Select

# What a cell may hold once it leaves an adapter. Driver types do not escape this package
# (standards/fastapi.md); `object` would only push the guessing up to every caller, and reach
# TypeScript as `unknown`. Beyond the primitives, dates and Decimals are what the drivers
# actually hand back.
CellValue = datetime | date | Decimal | bool | int | float | str | None
Row = dict[str, CellValue]


class DataSource(Protocol):
    async def run(self, statement: Select[Any]) -> list[Row]:
        """Execute a read-only SELECT statement (values bound in it) and return rows."""
        ...
