# Corelantic MVP — Architecture (Draft)

## Principles

- **Build the seams, not the implementations.** Abstract where retrofitting later is expensive (data source, LLM provider, chart spec, identity); hardcode everything else.
- **One process, full capability.** The agent runs in-process inside FastAPI. That is a *deployment* choice, not a capability limit — multi-model orchestration and parallelism still happen, just in one service. Extraction to a standalone agent runtime (e.g. GCP Agent Engine) stays possible because the orchestrator sits behind a clean internal boundary.
- **Portable by default.** A single container runs on Azure or GCP, so infra decisions don't block the build.
- **The browser trusts nothing.** Same BFF model as KRW: the browser only talks to the web app; the web app calls the API server-to-server.

## Components

```
                          Browser (Corelantic UI)
                                   │  (session cookie only)
                                   ▼
                    ┌──────────────────────────────┐
                    │  Web — Next.js (App Router)   │  owns Entra session, renders shell
                    │  · Auth.js + Microsoft Entra  │  BFF: server-side calls to the API
                    └──────────────┬───────────────┘
                                   │  server-to-server (internal auth)
                                   ▼
        ┌────────────────────────────────────────────────────────┐
        │  API — FastAPI (async, uv)                              │
        │                                                        │
        │  routes ── catalog · query ────┐                        │
        │        └── nlq/ask ────────────┤                        │
        │                                ▼                        │
        │   services/                 orchestrator (agent)        │
        │     semantic/   ── metric & dimension registry          │
        │     query/      ── structured-intent → SQL compiler      │
        │     charts/     ── result → ECharts spec                 │
        │     ai/         ── LLM provider interface (Claude…)      │
        │     data/       ── data-source adapter (Azure SQL)       │
        └───────────────────────────┬────────────────────────────┘
                                     │  read-only, least-privilege
                                     ▼
                        Azure SQL  (KRW analytics DB, or replica/views)
```

## Two request paths

### 1. Dashboard (deterministic)

The dashboard is **not** agent-composed in this cut. Each of the nine visuals maps to a named metric in the semantic layer. The frontend posts a structured intent — the same shape the agent plans — and the API validates it against the registry, compiles it to parameterized SQL, runs it read-only, and returns rows with the schema that describes them.

```
UI visual ──POST /query {metric, grain, filters, compare}──▶ API
   API: validate against registry → SQL compiler → Azure SQL (read-only) → rows
   API: rows + column schema + the intent as run ──▶ UI renders
```

`GET /catalog` publishes what may be asked of each metric — its groupable dimensions, the dates
it can anchor on, and whether it admits `compare` or `accumulate` — so the controls populate
themselves rather than hardcoding a list. Cross-filtering and time-grain are fields of the
intent; no new visual types, no LLM.

### 2. NL analytics (agentic)

```
User question
   ▶ orchestrator plans: which metric(s)/dimension(s)/filters? (LLM, constrained to the
     semantic registry)
   ▶ emits a STRUCTURED QUERY INTENT (metric, dimensions, filters, grain) — not raw SQL
   ▶ query compiler turns intent into parameterized, read-only SQL
   ▶ execute against Azure SQL → rows
   ▶ chart service → ECharts spec; LLM → 1–2 sentence narrative grounded in the rows
   ▶ stream chart + narrative back to the panel (SSE)
```

The LLM chooses *what to ask*, from a closed vocabulary. It does **not** hand-write SQL that we execute blindly (see [`data-and-semantic-layer.md`](./data-and-semantic-layer.md) for why, and the guarded raw-SQL fallback).

## The chart-spec contract

Both paths produce the **same** ECharts spec shape, rendered by one `<Chart>` component. This is what makes the dashboard and the agent's answers visually identical and is the single most important abstraction for "feels like one product." It's also the seam that milestone-2 "add to dashboard" will reuse: persisting an agent answer is persisting its chart spec.

## Interfaces we commit to now (one impl each)

| Interface           | MVP implementation        | Why it's a seam                                  |
| ------------------- | ------------------------- | ------------------------------------------------ |
| `DataSource`        | Azure SQL (read-only)     | Add Postgres/BigQuery/other clients without app changes |
| `LLMProvider`       | Claude (Anthropic)        | Gemini / SLMs / model routing without app changes |
| `IdentityProvider`  | Microsoft Entra (OIDC)    | Add other IdPs / own-auth later                  |
| `ChartSpec`         | ECharts spec              | Shared by dashboard + agent; reused by later features |

## What we are NOT abstracting yet

Multi-tenancy, connector marketplace, per-user personalization, a background job/worker tier, a persistent app database. The MVP is effectively stateless beyond the Entra session and the read-only source — no app DB is required for this cut. If we later add chat history or saved charts, a small Postgres appears then, not now.

## Security posture (carried over from the KRW review)

- BFF boundary with an internal shared secret on the web→API hop; constant-time check.
- Server-only secret handling; no tokens or DB credentials reach the browser bundle.
- DB account is **read-only, least-privilege**, distinct from the ETL/writer account.
- The semantic layer + intent compiler are the SQL trust boundary — the LLM cannot reach arbitrary tables or emit destructive statements.
