# Corelantic — API

FastAPI service for the Corelantic MVP: dashboard metrics (deterministic) and the natural-language analytics agent. Managed by `uv`; never use bare `pip`/`python`. Read [`../../standards/fastapi.md`](../../standards/fastapi.md) before changing it.

## Layout

```
app/
  main.py            application factory and wiring
  core/config.py     typed settings (CORELANTIC_API_ prefix)
  api/               routes (HTTP only) + dependency wiring
  schemas/           request/response contracts
  services/          business logic; services/agent/ is the NL orchestrator
  semantic/          registry models + YAML loader (the business vocabulary)
  query/             the structured intent and the SQL compiler (trust boundary)
  adapters/          swappable seams: data/ (DataSource), llm/ (LLMProvider) + factory
semantic/            metric & dimension definitions (YAML) — placeholder pending O-2
tests/
```

Dependency flow is one-way: `routes → services → (semantic / query / adapters)`.

## Getting started

```bash
cp .env.example .env      # fill in as credentials become available
uv sync                   # install (creates .venv)
uv run corelantic-api     # serve on :8080  (docs at /docs)
```

Or from the repo root: `make install`, then `make dev-api`.

## Checks

```bash
uv run ruff check .
uv run ruff format .
uv run mypy
uv run pytest
```

`make check` (repo root) runs lint + typecheck + tests across both apps.

## Current state

The health endpoint and the metric *listing* work today. Reading metric data and the NL agent return **503** until their providers are provisioned: the Azure SQL data source (docs O-1) and the Claude LLM key. The semantic registry ships a clearly-marked **placeholder** (`semantic/leads.example.yaml`) so the API runs end to end; it is replaced with real definitions once the KRW schema is available (docs O-2).
