"""A DataSource backed by seeded, in-process SQLite — no external dependency.

Turns every metric read into real numbers (KRW-ballpark) so the dashboard and NL panel are
demoable while the Azure SQL replica is still pending (docs O-1). It implements the same
``DataSource.run(statement)`` contract the Azure adapter (C2) will, so swapping to the real
replica is a config choice — the compiled statement is dialect-neutral and runs unchanged.

The engine is an in-memory SQLite kept alive by a single pooled connection (StaticPool), so
the seed persists for the process. The registry's sources are schema-qualified
(``gold_tspot.cases``), so we ATTACH a ``gold_tspot`` database to resolve them. Reads run
on a worker thread to honour the async contract without blocking the event loop.
"""

import asyncio
import threading
from typing import Any

from sqlalchemy import Select, create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool

import app.adapters.data.sqlite  # noqa: F401 — registers the DateBucket SQLite rendering
from app.adapters.data.seed import SCHEMA, build_rows

_SCHEMA_NAME = "gold_tspot"


class FixtureDataSource:
    def __init__(self, *, leads: int = 86_000, seed: int = 20260707) -> None:
        self._engine = create_engine(
            "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
        )
        # StaticPool shares one physical connection; serialize reads so concurrent
        # requests (run on worker threads) never use it simultaneously.
        self._lock = threading.Lock()
        self._seed(leads, seed)

    def _seed(self, leads: int, seed: int) -> None:
        rows = build_rows(leads, seed)
        with self._engine.begin() as connection:
            connection.execute(text(f"ATTACH DATABASE ':memory:' AS {_SCHEMA_NAME}"))
            for table, columns in SCHEMA.items():
                column_list = ", ".join(columns)
                connection.execute(text(f"CREATE TABLE {_SCHEMA_NAME}.{table} ({column_list})"))
                if rows[table]:
                    binds = ", ".join(f":{column}" for column in columns)
                    insert = f"INSERT INTO {_SCHEMA_NAME}.{table} ({column_list}) VALUES ({binds})"
                    connection.execute(text(insert), rows[table])

    async def run(self, statement: Select[Any]) -> list[dict[str, object]]:
        # SQLite/pysqlite is blocking; run off the event loop to honour the async contract.
        return await asyncio.to_thread(self._run, statement)

    def _run(self, statement: Select[Any]) -> list[dict[str, object]]:
        with self._lock, self._engine.connect() as connection:
            return [dict(row) for row in connection.execute(statement).mappings().all()]

    @property
    def engine(self) -> Engine:
        return self._engine
