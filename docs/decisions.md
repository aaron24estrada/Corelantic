# Corelantic MVP — Decisions & Open Questions (Draft)

Last updated 2026-07-03. Captures what's settled, what's still open, and what's explicitly deferred, so we don't re-litigate or drift. Grounded in the 2026-06-22 call and the follow-up technical review.

## Settled decisions

**D-1 — Custom build, no Power BI or ThoughtSpot dependency.** The MVP reproduces the embedded experience with our own dashboard and our own NL analytics. Rationale: remove vendor lock-in, own the model layer, and be able to scale to other clients on our own stack. Agreed by all three on the call.

**D-2 — Mirror the embedded system, nothing more.** Scope is bounded to the nine visuals of the current KRW dashboard plus one NL analytics panel. Add-to-dashboard, reports/decks, personalization, multi-connector, and multi-tenant are out. Rationale: validate that we can rebuild the embedded system as a custom one before investing in breadth.

**D-3 — Single data source, read directly.** Read KRW's existing Azure SQL read-only for the MVP; do not copy, sync, transform, or rebuild ingestion. Imran's ETL already curates the data. We design the data-access layer behind an interface so swapping to a replica or a copy later is invisible to the app.

**D-4 — Reuse Entra SSO; do not build custom auth.** Login is Microsoft Entra ID via Auth.js, behind a thin identity interface. Rationale: KRW users already have Microsoft identities, it's what "mirror the embedded experience" implies, and it's the lowest-friction path. Rolling our own credential/session/password auth adds security risk with no lock-in benefit — anti-lock-in belongs at the data-source and model-provider layers, not auth. Own-auth / multi-IdP is a productization-phase concern (deferred). This overrides the initial "should we build custom auth?" instinct.

**D-5 — Self-contained, portable backend.** One async FastAPI service with the agent orchestrator in-process, shipped as a container that runs unchanged on Azure or GCP. Rationale: right altitude for validation, keeps full orchestration capability, and de-risks the still-open Azure-vs-GCP infra decision by not depending on it.

**D-6 — Anti-lock-in via interfaces, one implementation each.** `DataSource`, `LLMProvider`, `IdentityProvider`, and a shared `ChartSpec` are the seams we commit to now; we implement Azure SQL, Claude, Entra, and ECharts respectively, and nothing more. Rationale: build the seams, not speculative implementations.

**D-7 — Structured query intent, not LLM-authored SQL.** The model plans queries from the semantic registry and emits a validated intent object; we compile the SQL. Rationale: safety, metric correctness, and debuggability. A guarded raw-SQL fallback is left as a later option, not built now.

**D-8 — Apache ECharts as the single chart-spec contract.** *Confirmed 2026-07-10, closing O-5.* Both the dashboard and the agent render through one chart component and one spec shape, so the two surfaces look identical.

We stopped waiting on Imran to confirm his agent's format, because waiting inverted D-6. `ChartSpec` is one of the four seams **we** own; which library it renders through is an implementation detail *behind* that seam, and an agent that emits some other shape is an adapter at the boundary — the same shape as the `DataSource` adapter we have now written twice. The consumer did not even exist yet: the agent is blocked on E1. Four issues were held hostage to a format question about a component nobody had written.

The spec is cheap to build because `POST /query` returns a `ResultSet` whose columns carry a `role` (period / dimension / metric / previous / delta) and a `format` (number / currency / percent / percent_point). A chart spec is a pure function of that result plus the intent that produced it, so the deterministic dashboard and an agent answer reach `<Chart>` by the same path.

## Open questions (need answers before or during the build)

**O-1 — What exactly is the Azure SQL, and can we get a read-only credential?** "Azure SQL Express" is ambiguous (SQL Server Express on a VM vs. managed Azure SQL Database). This determines connection strategy and whether we need a replica/views to avoid loading production. Owner: Imran. Blocks M2.

**O-2 — Schema and existing metric definitions for the nine visuals.** *Partially answered 2026-07-05* — the KRW semantic model (tables, columns, measure names) is captured in [`data-model.md`](./data-model.md). That gives the structure and metric vocabulary. Still needed: the **measure formulas** (how `Cost per Lead`, `ROAS`, funnel rates, WoW/MoM are computed) so ours match KRW's numbers; confirmation of **which objects are queryable SQL** (vs Power-BI-only computed tables) with real names; and the two date roles (lead vs referral). Owner: Imran. Blocks the real semantic registry (currently a placeholder) for M2/M3.

**O-3 — Deploy target: Azure or GCP.** Parked for Dom/Imran. Not blocking, because D-5 makes the build portable — but it should be settled before we stand up production infra.

**O-4 — Is this cut single-tenant KRW only, or must it already be sellable to non-Microsoft firms?** If the latter, D-4 changes (we'd want our own IdP now, not just Entra). Current assumption: single-tenant KRW, Entra is fine. Confirm with Aaron/Dom.

**O-5 — Chart library confirmation.** *Resolved 2026-07-10 — see D-8.* We use [Apache ECharts](https://echarts.apache.org). Imran's agent no longer gates it.

## Explicitly deferred (not now, but the design leaves room)

Add-to-dashboard (persist an agent-built chart via its chart spec) — milestone 2. Report / slide-deck generation (NotebookLM / Nano Banana style) as an agent tool. Personalization and per-user RAG corpus. Multi-source ingestion and self-service connectors. Multi-tenant control plane. Chat history persistence — note it is nearly free once we own the store (a small Postgres), and is coincidentally the feature currently blocked on the embedded KRW build; we may choose to include it as a low-cost parity win, but it is out of the strict MVP scope.

## Notes carried from the code review

The KRW app's BFF security model (browser → web → API server-to-server, internal shared secret, constant-time check, server-only secrets, no credentials in the browser bundle) is sound and should be carried over. The corelantic-poc shipped with no authentication at all — that must not recur here; D-4 is the guard.
