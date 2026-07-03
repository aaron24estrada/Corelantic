# Corelantic

A productized analytics platform: sign in once, see an executive dashboard, and ask questions of your data in natural language — one branded surface we own end to end. The first MVP is a **custom replica of the KRW Analytics embedded experience** (SSO → dashboard → conversational analytics) with **no Power BI or ThoughtSpot dependency**, reading a single Azure SQL source. See [`docs/`](docs/) for the full plan.

Monorepo (planned): `apps/web` (Next.js, App Router) and `apps/api` (FastAPI, uv-managed), with a `semantic/` registry of metric and dimension definitions.

## Specification (read for context)

The MVP is specified in [`docs/`](docs/). Read [`docs/README.md`](docs/README.md) first; it orders the rest. The load-bearing decisions:

- Custom build, single data source (KRW's Azure SQL, **read-only**), portable FastAPI backend with the agent **in-process**, custom React dashboard + custom NL analytics panel.
- Reuse **Entra SSO**; do not build custom auth. Anti-lock-in lives at the data-source and model-provider seams, not auth.
- The model **plans** queries from the semantic layer and emits a validated structured intent; it never emits SQL we execute directly.
- Out of this cut: add-to-dashboard, report/deck generation, personalization, multi-connector, multi-tenant.

Open questions and the settled-vs-deferred split live in [`docs/decisions.md`](docs/decisions.md).

## Coding standards (read on demand)

Enforced standards live in [`standards/`](standards/). Before writing or reviewing code, open the file that applies and follow it. Do not inline these into context preemptively; read the one you need when you need it.

- All code: [`standards/principles.md`](standards/principles.md) — naming, structure, **modularity and boundaries**, and the **trust boundaries** (read-only DB, model-plans-never-executes, untrusted model output, secrets).
- `apps/api` (FastAPI / Python): [`standards/fastapi.md`](standards/fastapi.md).
- `apps/web` (Next.js / TypeScript): [`standards/nextjs.md`](standards/nextjs.md).

## Build and checks

- Python is uv-only. Never call bare `pip` or `python`. Use `uv run` and `uv add`.
- Run `make check` (ruff, mypy `--strict`, eslint, tsc, pytest) before committing. Passing the tools is the floor, not the goal.

## Conventions in one breath

Depend on interfaces, not vendors — `DataSource`, `LLMProvider`, `IdentityProvider` behind factories, one implementation each, vendor SDKs confined to their adapter. One-way dependency flow: `routes → services → (semantic / query / adapters)`. Everything swappable is a config choice. Comments explain why, not what. Type everything; no `Any`/`any`. Fail loudly at boundaries. Secrets never reach source control, logs, or the client bundle.
