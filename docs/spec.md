# Corelantic MVP — Specification (Draft)

## Summary

A custom, self-owned analytics platform that reproduces the KRW Analytics embedded experience without embedding anyone else's product. A signed-in user lands on an **executive overview dashboard** and can **ask questions of the same data in natural language**, getting back charts and short narratives — all in one Corelantic-branded surface.

The MVP proves one thing: **we can replicate the embedded (Power BI + ThoughtSpot) experience as a fully custom build, from a single data source.** Success is Aaron opening it and saying "this looks the same or better" — for both the dashboard and the chat.

## Why we're building it (from the 2026-06-22 call)

- **Own the stack, remove vendor lock-in.** Today KRW is Power BI + ThoughtSpot glued together. Going custom removes dependency on either vendor's roadmap and pricing, and lets us control the model layer (multi-provider, model fragmentation, SLMs).
- **The agent is the core product; the dashboard is table-stakes.** Executives expect a dashboard, so we give them one — but the durable value is conversational, multimodal analytics. This MVP builds the minimum of both.
- **Validate before we generalize.** Rather than build a heavy multi-connector product speculatively, mirror the one thing that already works and learn where the hard parts are.

## Goals (MVP)

- **Single sign-on** — one login (reuse Microsoft Entra ID, as KRW does today).
- **Custom executive dashboard** — a hand-built, deterministic set of visuals bound to the KRW data, replacing embedded Power BI. Time-grain filtering and cross-filtering.
- **Custom NL analytics panel** — natural-language questions answered with a generated chart + short narrative, replacing embedded ThoughtSpot Spotter.
- **One coherent, branded front end** — both surfaces share a single theme so it reads as one product, not assembled parts.
- **Single data source** — read KRW's existing Azure SQL directly (read-only).
- **Swappable seams** — data source and LLM provider behind interfaces; one implementation each for now.

## Non-Goals (MVP) — deliberately deferred

- **Add-to-dashboard from chat** (persisting agent-built charts). Milestone 2.
- **Report / slide-deck generation** (NotebookLM / Nano Banana style). Later.
- **Personalization / per-user RAG corpus.** Later.
- **Multi-source ingestion / self-service connectors.** One source only.
- **Multi-tenant control plane.** Single client (KRW) only.
- **Rebuilding ingestion / ETL.** Imran's pipeline already populates Azure SQL; we read from it, we do not own or transform the source.
- **Chat history persistence.** Out of scope for parity (though nearly free in a custom build — see [`decisions.md`](./decisions.md), deferred list).

## Scope — exactly what "mirror the embedded system" means

The embedded KRW dashboard (per its mockup) is the concrete target. Nothing more.

**Executive overview**

- Four KPI tiles with sparklines: **New leads**, **Signed cases**, **Cost per lead**, **Marketing spend**.
- Five visuals: **Leads by week**, **Leads by channel** (Facebook / Google / Referral / Linear TV / Website), **Lead → signed** funnel, **Top regions** (Texas metros), **Recent intakes** table.
- A global **time-grain filter** (week / month) and **cross-filtering** (clicking a channel or region filters the rest).

**Ask your data** (the Spotter mirror)

- A prompt box + example chips. A question returns a single generated chart and a one-to-two-sentence narrative grounded in the query result.
- Responses stream. No saved history in this cut.

Anything outside these is out of scope for the MVP.

## Users

- **KRW executives** — view the dashboard and ask questions. Single role for the MVP.

## Data context

Source data (Law Ruler CRM, marketing/ads APIs, Zoom) is ingested by the data team's existing ETL into an **Azure SQL** database that Imran owns. Power BI and ThoughtSpot already model it. Corelantic reads that database directly (read-only) for the MVP and does not transform the source. Exact edition and schema are pending (see [`decisions.md`](./decisions.md), O-1 / O-2).

## Authentication

- **App login:** Microsoft Entra ID (OIDC) via Auth.js in the web layer — the same approach KRW uses, behind a thin identity interface so other IdPs can be added later.
- No second login: unlike the embedded app, there is no ThoughtSpot/Power BI identity to reconcile, so auth is simpler than KRW's (no per-user embed tokens to mint).
- We are **not** building bespoke credential/session/password auth. See [`decisions.md`](./decisions.md), D-4.

## Tech stack (proposed)

| Layer            | Choice                                   | Reason                                                        |
| ---------------- | ---------------------------------------- | ------------------------------------------------------------ |
| Frontend + auth  | Next.js 16 (App Router) + TypeScript     | Reuse the poc/KRW pattern; SSR shell; first-class Entra login |
| App auth         | Auth.js + Microsoft Entra ID             | One login; web layer holds the session (BFF)                 |
| Styling / UI     | Tailwind v4 + shadcn/ui                   | Reuse the poc component library and theming                  |
| Charting         | **ECharts** (`echarts-for-react`)        | One chart-spec format shared by dashboard **and** agent output |
| Backend          | FastAPI (async, uv-managed)              | Reuse the poc skeleton; agent runs in-process; portable       |
| DB access        | SQLAlchemy Core (async) → Azure SQL      | Read-only, parameterized; adapter interface for other sources |
| Agent / LLM      | Provider interface, Claude default       | Anthropic SDK; Gemini-ready; model routing in-process         |
| Semantic layer   | Hand-authored metric/dimension defs (YAML) | Constrains NL querying to safe, correct queries              |

Charting note: ECharts is chosen deliberately because Imran's agent already emits ECharts-style specs. A single "chart spec" contract means the static dashboard and the agent-generated charts render through the same component and look identical — which is what makes it feel like one product.

## Deployment

A single containerized FastAPI service plus the Next.js app. The container runs on **Azure or GCP** unchanged, so the Azure-vs-GCP decision (Imran/Dom) does **not** block this build. See [`decisions.md`](./decisions.md), O-3.

## Proposed repository layout

```
corelantic/
├── docs/            # this specification set
├── apps/
│   ├── web/         # Next.js — UI, Entra session, BFF
│   └── api/         # FastAPI — dashboard metrics + NL analytics agent (uv-managed)
├── semantic/        # metric & dimension definitions (YAML) for the KRW dataset
└── README.md
```

## Milestones

| ID | Deliverable                                                                            |
| -- | -------------------------------------------------------------------------------------- |
| M1 | Monorepo + app shell + Entra login (BFF), Corelantic theme                              |
| M2 | Read-only Azure SQL connection + semantic layer for the KRW dataset                     |
| M3 | Custom executive dashboard (4 KPIs + 5 visuals) with time-grain + cross-filter          |
| M4 | NL analytics panel: question → structured query → chart + narrative, streaming          |
| M5 | Combined, themed layout; internal UAT; demo-ready for Aaron/Matt                         |

## Open risks (see linked docs)

1. **NL fidelity vs. Spotter.** Raw text-to-SQL underperforms ThoughtSpot's semantic model. Mitigated by the semantic layer — this is the real work, not the dashboard. See [`data-and-semantic-layer.md`](./data-and-semantic-layer.md).
2. **Querying a live production DB.** Ad-hoc agent queries against KRW's prod Azure SQL could affect their ETL / Power BI / ThoughtSpot. Mitigated by read-only least-priv access and, ideally, a replica or curated views.
3. **"Mirror" scope creep.** Bounded strictly to the nine visuals above.
