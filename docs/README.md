# Corelantic — MVP Docs

Corelantic is a productized analytics platform: sign in once, see an executive dashboard, and ask questions of your data in natural language — all in one branded surface that we own end to end.

This first MVP is a **custom replica of the KRW Analytics embedded experience**, with **no dependency on Power BI or ThoughtSpot**. Same felt experience (SSO → dashboard → conversational analytics), but every layer is ours. The point is to *validate that we can rebuild the embedded system as a custom one from a single data source* — and in doing so, learn exactly where custom is worth it before we invest in the generalized, multi-connector, multi-tenant product.

> Status: **draft**. Last updated 2026-07-03. This maps to the direction agreed in the 2026-06-22 call (Aaron / Imran / Zain) and the follow-up technical review.

## Read in this order

1. [`concepts.md`](./concepts.md) — the three ideas the architecture rests on (definitions-not-data, model is visual-independent, model is schema-bounded). Read first; they're not obvious from the code.
1. [`spec.md`](./spec.md) — the MVP specification: goals, non-goals, scope, milestones.
2. [`architecture.md`](./architecture.md) — components, boundaries, request/data flow.
3. [`data-and-semantic-layer.md`](./data-and-semantic-layer.md) — how we read Azure SQL safely, and the semantic layer that makes NL querying trustworthy. **The main risk lives here.**
4. [`nlq-pipeline.md`](./nlq-pipeline.md) — the agentic natural-language → analytics flow.
5. [`decisions.md`](./decisions.md) — what's settled, what's open, and what's deferred.
6. [`data-model.md`](./data-model.md) — the KRW semantic model (real tables, columns, and measures) the build reproduces.
7. [`status.md`](./status.md) — current state, blockers, and next steps (start here to continue).

## One-line summary of the decisions

Custom build, **single data source** (KRW's Azure SQL, read-only), a **portable FastAPI backend** with the agent in-process, a **custom React dashboard** and a **custom NL analytics panel** — reusing KRW's **Entra SSO**, with data-source and model-provider behind **swappable interfaces** so we avoid lock-in where it actually matters. Explicitly *not* in this cut: add-to-dashboard, report/deck generation, personalization, multi-connector, multi-tenant.
