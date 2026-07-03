# FastAPI / Python Standards

Applies to `apps/api`. Read [principles.md](principles.md) first. Python is managed by uv — never call bare `pip` or `python`.

## Tooling

- Use uv for everything: `uv add`, `uv add --dev`, `uv run`.
- `ruff` (lint and format), `mypy --strict`, and `pytest` must pass before commit. `make check` runs them.
- Declare runtime dependencies in `[project.dependencies]`, dev tools in `[dependency-groups].dev`.

## Layout and layering

```
app/
  main.py            application factory and wiring only
  core/config.py     typed settings (env-prefixed)
  api/router.py      aggregates the route modules
  api/routes/        one module per resource, HTTP concerns only
  services/          business logic and orchestration, no FastAPI imports
    agent/           the NL analytics orchestrator and its tools
  semantic/          metric and dimension registry, loaded from semantic/*.yaml
  query/             structured-intent validation and the SQL compiler
  adapters/          swappable implementations behind interfaces
    data/            data-source adapters (Azure SQL)
    llm/             LLM provider adapters (Claude, …)
```

Dependencies flow one direction: `routes → services → (semantic / query / adapters)`. Never the reverse.

- Routes are thin. They validate input through the request model, call a service, and return a response model. No business logic, no SQL, no external calls in a route.
- Services hold business logic and orchestration. They are framework-agnostic: no `Request`, no `HTTPException`. They raise domain errors.
- Adapters each wrap one external system behind an interface. They are created once and reused (see Async and IO), not constructed per request.

## Interfaces and providers

- Anything swappable is an abstract interface (a `Protocol` or ABC) in the layer that owns it, with implementations in `adapters/`. This applies at least to `DataSource`, `LLMProvider`, and `IdentityProvider`.
- A factory selects the implementation from settings (`DATA_SOURCE`, `LLM_PROVIDER`, …). Application code depends only on the interface and is injected the chosen implementation via `Depends`.
- Vendor SDKs are imported only inside their adapter. No `anthropic`, no database driver import, anywhere else.

## Data source access

- All source-data reads go through the `DataSource` interface. No service opens a raw connection.
- The connection uses a **read-only, least-privilege** account, distinct from any ETL/writer account. It may read only an allowlisted set of tables or views.
- Every query is parameterized, `SELECT`-only, and bounded by a statement timeout and a hard row cap. Never build SQL by string concatenation of untrusted values.
- The adapter returns typed rows, not driver cursors. Driver types do not escape `adapters/data/`.

## Semantic layer

- The semantic registry (`semantic/*.yaml`) is the single source of truth for metrics, dimensions, synonyms, and constraints. Both the deterministic dashboard and the agent read from it.
- Metric and dimension definitions live in YAML and are loaded and validated into typed models at startup. No metric formula is hardcoded in a service or a route.
- The SQL compiler turns a validated `(metric, dimensions, filters, grain)` intent into parameterized SQL using only registry-defined sources and expressions. It is a pure function, unit-tested without a database.

## The agent

- The orchestrator lives in `services/agent/`. It plans a query from the semantic registry and emits a **structured query intent** validated against the registry. It never emits SQL that we execute directly.
- Every field of an intent is validated against the registry before compilation. An unmatched metric or dimension is a clear, user-facing "not supported" — never a guess.
- Narratives are generated strictly from returned rows and must not assert numbers absent from the result set.
- LLM calls go through the `LLMProvider` interface so model routing (cheap model for planning/narrative, stronger only when needed) is a config and orchestration concern, not scattered SDK calls.
- Long responses stream to the client (SSE). Do not block a request for the full generation when you can stream.

## Endpoints

- Resource-oriented, plural nouns, lowercase, kebab-case for multiword paths: `/metrics`, `/nlq/ask`.
- Identify items with path params (`/metrics/{metric_name}`). Filter and shape with query params (`/metrics/new_leads?grain=week&channel=Facebook`).
- Use HTTP methods for intent: GET (read, no side effects), POST (create or action). Non-CRUD actions are a named sub-resource.
- Group a resource's routes in one module with a shared `APIRouter(prefix=..., tags=[...])`. Tags drive the generated docs.
- Status codes are explicit and correct: 200 read, 201 create, 4xx client error, 5xx server error. Never return a 200 with an error payload.

## Request and response models

- Every request body and every response is a Pydantic model. Never accept or return a raw `dict`.
- Keep the API contract separate from internal or domain models. Do not expose an internal model directly as the API shape.
- Declare the response model on every route so the schema is validated and documented. Every field is typed and annotated with `Field(description=...)`; the goal is that the generated `/docs` explains itself.
- Use `StrEnum` for closed sets, timezone-aware `datetime` (UTC) for times, and precise types for ids. No `Any`.
- Custom OpenAPI operation ids (`{tag}-{function_name}`) so the generated typed client is clean.

## Errors

- Services raise domain exceptions. A single exception handler maps them to HTTP responses with a consistent error body. Routes may raise `HTTPException` for simple, local cases.
- Do not leak stack traces, secrets, connection strings, or internal identifiers to clients or logs.

## Settings

- All configuration goes through the `pydantic-settings` layer in `core/config.py`, env-prefixed (`CORELANTIC_API_`). No `os.getenv` scattered through the code.
- Read settings through the `get_settings()` accessor or a dependency, not via module-level reads.

## Async and IO

- Endpoints and service methods that perform IO are `async`. Use async DB and HTTP clients. Do not block the event loop with sync `requests`, `time.sleep`, or sync file IO in request paths.
- Offload unavoidable blocking calls with `asyncio.to_thread`.
- Create shared clients and the DB engine once at startup (lifespan) and inject them. Do not construct a new client per request.

## Tests

- pytest. Test the HTTP contract (status code, response model), service behavior, and — most importantly — the pure query/semantic logic.
- One behavior per test, descriptive names, arrange/act/assert.
