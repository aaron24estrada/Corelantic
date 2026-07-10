"""What a result row holds once it leaves the data source.

A row is the output of a compiled query, so its shape belongs to ``query`` rather than to any
adapter or to the API schema. Both depend on it: the adapters promise to return this and
nothing driver-shaped (standards/fastapi.md), and the API contract publishes it. `object` would
have satisfied neither — it reaches TypeScript as `unknown` and pushes the guessing to every
call site.
"""

from datetime import date, datetime
from decimal import Decimal

CellValue = datetime | date | Decimal | bool | int | float | str | None
Row = dict[str, CellValue]
