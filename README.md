# Corelantic

A productized analytics platform: sign in once, see an executive dashboard, and ask questions of your data in natural language — one branded surface, owned end to end.

The first MVP is a **custom replica of the KRW Analytics embedded experience** (SSO → dashboard → conversational analytics) with **no Power BI or ThoughtSpot dependency**, reading a single Azure SQL source. It exists to validate that we can rebuild the embedded system as a fully custom one before investing in the generalized, multi-connector, multi-tenant product.

> Status: **early setup.** The plan is written; the apps are not scaffolded yet. See [`docs/`](docs/).

## Layout

```
corelantic/
├── docs/         MVP specification set — read docs/README.md first
├── standards/    engineering rules (clear, semantic, modular) — read on demand
├── apps/
│   ├── web/      Next.js (App Router) — UI, Entra session, BFF   [planned]
│   └── api/      FastAPI (uv-managed) — metrics + NL analytics agent   [planned]
├── semantic/     metric & dimension definitions for the dataset   [planned]
├── CLAUDE.md     project entry point for agents and contributors
└── SECURITY.md   secrets, data access, and trust-boundary rules
```

## Documentation

- [`docs/`](docs/) — the MVP specification: [spec](docs/spec.md), [architecture](docs/architecture.md), [data & semantic layer](docs/data-and-semantic-layer.md), [NL pipeline](docs/nlq-pipeline.md), and the [decision log](docs/decisions.md).
- [`standards/`](standards/) — how we write code here. Start with [principles](standards/principles.md).
- [`CLAUDE.md`](CLAUDE.md) — the one-page orientation.

## Prerequisites

- [uv](https://docs.astral.sh/uv/) for Python (never bare `pip`/`python`). Python pinned in `.python-version`.
- Node pinned in `.nvmrc`.

## Development

Common tasks run from the repo root via `make`, each delegating to the right app:

```bash
make install     # install dependencies for both apps
make lint        # ruff (api) + eslint (web)
make format      # ruff format (api) + prettier (web)
make typecheck   # mypy --strict (api) + tsc (web)
make test        # pytest (api)
make check       # lint + typecheck + test
```

Run `make check` before committing. Passing the tools is the floor, not the goal.
