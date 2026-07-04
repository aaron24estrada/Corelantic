# Status & Handoff

Last updated 2026-07-05. A snapshot of where the build is, what's verified, what's blocked, and what to do next — written so a fresh session can continue without prior context. Decisions and their rationale live in [`decisions.md`](./decisions.md); this is the "where are we / what next" view.

## Built so far

- **Docs** — the MVP spec set ([spec](./spec.md), [architecture](./architecture.md), [data & semantic layer](./data-and-semantic-layer.md), [NL pipeline](./nlq-pipeline.md), [decisions](./decisions.md)).
- **Foundation** — `standards/` (code rules), `CLAUDE.md`, repo hygiene (`.gitignore`, version pins, `Makefile`, `SECURITY.md`, `README.md`).
- **`apps/api`** (FastAPI, uv) — semantic-layer models + YAML loader; the query compiler (structured intent → parameterized SQL, the trust boundary); `DataSource`/`LLMProvider` seams + config factory; metrics service + agent orchestrator; thin routes under `/api/v1`. Internal BFF-secret auth (fail-closed) and structured JSON logging with per-request ids.
- **`apps/web`** (Next.js 16, React 19, Tailwind v4) — runnable skeleton; the typed API client generated from the OpenAPI schema; the BFF boundary (server-only client + `/api/bff` proxy); a server-rendered `/dashboard` listing the metric catalog.

Everything is committed and pushed to `origin/main`. Both apps pass their checks (`make check`).

## Verified working (runtime)

Health, metric listing, the BFF proxy (GET/POST), the SSR dashboard, internal-secret enforcement (401 wrong / 503 unconfigured / 200 with key), and per-request ids in logs. Metric *data* reads and the NL agent return an honest **503** until their providers exist.

## Blocked — needs answers/inputs (the real critical path)

- **O-1 — Azure SQL access.** Confirm the exact edition ("Azure SQL Express" is ambiguous) and get a **read-only, least-privilege credential**. Owner: Imran. Blocks real data.
- **O-2 — schema + metric definitions** behind the nine dashboard visuals, so the semantic layer matches what KRW already sees. Owner: Imran. Blocks the real semantic registry (currently a placeholder).
- **O-4 — auth.** Reuse Entra vs. Corelantic's own IdP. Owner: you/Dom. Blocks wiring the web login.
- **O-5 — chart format.** ECharts vs. whatever Imran's agent emits. Owner: Imran. Blocks the shared `<Chart>` contract.
- **O-3 — deploy target** (Azure vs GCP). Parked for Dom; not blocking (the build is portable).

## Next steps

Unblocked (safe to build now, no product decision):
- App shell + Corelantic brand theme + shadcn primitives + reusable error/empty/loading components.
- A **fixture `DataSource` adapter** (seeded JSON) so the dashboard and NL panel render before Azure SQL lands.
- CI running `make check` on PRs; pre-commit hooks; `.editorconfig`.
- Dockerfiles + local compose/Tilt to run web + api together.

Gated on decisions: dashboard visuals + NL panel (O-5), auth wiring (O-4), real KRW data (O-1/O-2).

## Running it locally

```bash
make install                 # both apps
make dev-api                 # API on :8080  (docs at /docs)
make dev-web                 # web on :3000
make client                  # regenerate the typed API client after API changes
make check                   # lint + typecheck + tests, both apps
```

Business API routes are **fail-closed**: set the same secret in both apps or they answer 503. In `apps/api/.env` set `CORELANTIC_API_INTERNAL_API_KEY`, and in `apps/web/.env.local` set `INTERNAL_API_KEY` to the same value. Copy each app's `.env.example` to start.
