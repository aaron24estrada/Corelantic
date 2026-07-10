# Status & Handoff

Last updated 2026-07-10. A snapshot of where the build is, what's verified, what's blocked, and what to do next — written so a fresh session can continue without prior context. Decisions and their rationale live in [`decisions.md`](./decisions.md); the real KRW schema lives in [`data-model.md`](./data-model.md); this is the "where are we / what next" view.

## The headline

**The backend is done for everything we can read.** The API serves **25 real metrics** over KRW's live Azure SQL (`gold_tspot`) through `POST /api/v1/query`, and the same registry runs against a seeded fixture that reproduces the source's numbers. Every metric on KRW's Executive Summary is reachable **except Spend and ROAS** — and that gap is an access grant, not code.

It was 30 until week-over-week and year-to-date stopped being *metrics*. `leads_wow_pct`, `leads_mom_pct`, `calls_wow_pct`, `leads_ytd` and `calls_mtd` are gone, replaced by `compare` and `accumulate` on the intent. That is a gain, not a loss: a comparison metric could only wrap a bare measure, so a week-over-week **voucher rate** or **revenue** was unrepresentable. Now **all 25** metrics can be compared and **17** can be accumulated, and one request returns the series, the value and the delta — a KPI tile used to need two.

## Built so far

- **Docs** — the MVP spec set ([spec](./spec.md), [architecture](./architecture.md), [concepts](./concepts.md), [data & semantic layer](./data-and-semantic-layer.md), [NL pipeline](./nlq-pipeline.md), [decisions](./decisions.md), [data-model](./data-model.md)).
- **Foundation** — `standards/`, `CLAUDE.md`, repo hygiene, pre-commit hooks.
- **`apps/api`** (FastAPI, uv) — the semantic layer and query engine, complete:
  - Four-type registry (entity / dimension / measure / metric), three metric shapes (simple, ratio, derived), plus **registry constants** and **filtered measures**.
  - Query compiler: structured intent → parameterized SQLAlchemy Core. Identifiers come only from the authored registry; values are always bound. **The model never emits SQL we execute.**
  - `POST /api/v1/query` takes an intent and returns a **`ResultSet`**: rows plus the column schema that describes them, plus the intent as it was actually run (relative window resolved to dates).
  - **Capability layer** (`semantic/capability.py`) — one implementation answering "what can this metric be asked" both as the predicate `validate_intent` enforces and as the projection `GET /api/v1/catalog` publishes, so the two cannot drift. A property test asserts a planner obeying the catalog can never be told 422.
  - `GET /api/v1/catalog` — every metric with its groupable dimensions, reachable date dimensions and supported modifiers; every dimension with its members; the closed enums for grain and relative range; and the calendar table saying which resets a grain may use.
  - Every bad intent is a **422** with a stable code and `allowed`: the vocabulary that would have worked. The agent repairs rather than retries.
  - Join graph with **cardinality-aware fan-out rejection**, LEFT OUTER fact→dimension joins, and date dimensions resolvable across a fan-out-free join.
  - Dialect-neutral time intelligence on the **intent** (grain, ranges, `compare`, `accumulate`) with SQLite **and** SQL Server renderings.
  - Two `DataSource` adapters behind one factory: **`azure_sql`** (real, Entra auth) and **`fixture`** (seeded in-memory SQLite).
- **`apps/web`** (Next.js 16, React 19, Tailwind v4) — runnable skeleton, typed API client from the OpenAPI schema, BFF boundary, SSR `/dashboard` listing the metric catalog. **No real UI yet** (epic D).

`make check` green: 223 tests. `make validate` green: 5 entities, 19 measures, 14 dimensions, 25 metrics, 1 constant across two registry files.

## Database access (O-1 — resolved)

Read-only access to KRW's warehouse, granted 2026-07-10.

- **Server** `krw-platform-sql.database.windows.net`, database `krw-platform`.
- **Auth** Entra ID, no SQL login. Dev uses device-code (interactive MFA) as `zain.hussain@krwlawyers.com`; the token is packed length-prefixed UTF-16LE and passed to ODBC. Needs `msodbcsql18` + `unixodbc-dev` installed locally.
- **Reachable from** two allow-listed IPs (a home IP and a static VPN IP). Work through the VPN — the home IP can rotate and the failure looks like a login error, not a network one.
- **Readable**: schema **`gold_tspot` only** (9 tables).
- **Deployed auth is unsolved**: a personal MFA account cannot authenticate headlessly. Production needs a **service principal / managed identity** with read-only `gold_tspot`. `azure_sql_auth_mode=service_principal` is already wired; the credential is not provisioned. Not a dev blocker; ask Imran.

## What the data actually is (O-2 — resolved for `gold_tspot`)

KRW is a **legal mass-tort referral practice** (asbestos/mesothelioma), not a generic marketing funnel. Three layers:

1. **Leads** — `cases` (86,973), `geo` (~38% of leads have **no** geo row — the dashboard's "(Blank)" bucket), channel via `source_category`.
2. **Intake funnel** — `stages`, one row per milestone reached: Lead → Voucher (24.2%) → X-Ray → B-Read → Clinic → Bank Complete (14.7%).
3. **Call centre** — `zoom_calls`, `agent_stats` (not on KRW's dashboard at all; pure upside).

Every metric definition was **verified against the live tables**, not inferred. Definitions that look obvious and are wrong are recorded in [`data-model.md`](./data-model.md); the load-bearing ones:

- A call was answered iff it has an **`answer_time`** (`COUNT` skips NULLs). Filtering `call_result = 'answered'` understates the rate ~4× — `connected` is the bigger bucket.
- `duration` is **seconds**, not milliseconds.
- Agent conversion is **pooled** `SUM(converted)/SUM(contacted)` = 4.44%. `agent_stats` is a per-agent-per-week rollup, so averaging its stored `conversion_rate_pct` gives 2.65% — a mean-of-ratios error.
- A `zoom_calls` row is a **call leg**, not a call (92,741 rows, 82,868 distinct `call_id`).
- `cases.Milestone` is *current* state, **not** the funnel. The funnel is `stages`.
- **Revenue is not stored**: Power BI computes it as `vouchers × $6,000`. That fee is a registry constant (`case_fee`), pending Imran's confirmation it's current.

## Blocked — the real critical path

- **Spend + Referrals (#37) — the only thing between us and the full dashboard.** `marketing_budget` (spend → **ROAS**, **Cost per Lead**) and `referral_leads` (cancer type, referral firm, fees) are **not in `gold_tspot`**. The `bronze_marketing`, `bronze_finance`, and `*_lawruler` schemas exist in the same database but this login cannot read them. Both originate as spreadsheets landed into the warehouse, so this is most likely an access grant, not a connector. Owner: **Imran**.
- **Deployed auth** — service principal for headless Azure SQL access (above). Owner: Imran.
- **O-4 — auth.** Reuse Entra vs. Corelantic's own IdP. Owner: you/Dom. Blocks the web login.
- **O-5 — chart format.** ECharts vs. whatever Imran's agent emits. Owner: Imran. Blocks the shared `<Chart>` contract.
- **E1 — Anthropic API key.** Blocks the NL agent (the planner can be built and tested against a fake).
- **O-3 — deploy target** (Azure vs GCP). Parked for Dom; not blocking.

## Next steps

Unblocked, highest value first:

1. **E2 — `plan_intent`** (question → validated intent), buildable against the `LLMProvider` interface with a fake, run against the fixture. `GET /catalog` gives the planner its vocabulary; the 422 body's `allowed` list lets it repair a bad intent instead of retrying blind.
2. **D2 / D4 / D5** — reusable states + `<Chart>`, the KPI row, core visuals. (D3/D6 gated on O-5.) D4's KPI tiles are now one request each: `compare` returns the series, the value and the delta together.
3. **A1 — CI running `make check` on PRs.** Note CI will need `msodbcsql18` + `unixodbc-dev` to build `pyodbc`. The suite is hermetic now (#48): it ignores `.env` and every `CORELANTIC_API_*` variable, so CI can set whatever it likes.
4. **#52 — calendar spine.** `compare` uses `LAG`, which reads the previous *populated* bucket, so a fully empty week is skipped rather than shown as a drop to zero.
5. **#53 — accumulation vs display window.** A running total must start on its reset boundary, so **D6's date-range control will 422 a "Revenue YTD" tile** the moment the picked range doesn't start on 1 January. Fix before D6, not after.

Gated: spend/referrals registry (#37), NL agent wiring (E1), auth (O-4), chart contract (O-5).

## Working agreements that paid off

- **Probe the database before authoring a metric.** Three definitions that looked obvious from column names were wrong by 4×, 1000×, and 2×. The probes cost minutes; the errors would have been invisible on a dashboard.
- **Run a codex architectural pass on every PR.** It caught five bugs that would have shipped silently: a Sunday-boundary week bucket in SQL Server, `LAG` reading across a NULL period, a registry constant shadowing a measure, a derived formula selecting an unaggregated literal, and a dark-mode focus ring that vanished while a button was held down. Redirect stdin or it hangs forever on `Reading additional input from stdin...`, and never pipe it through `tail` — `tail` buffers until the stream closes, so a hung run and a working one look identical:

  ```bash
  codex exec --sandbox read-only --skip-git-repo-check "$(cat prompt.txt)" < /dev/null > codex.log 2>&1
  ```
- **The test suite reads nothing from the machine.** `Settings` loads `.env` *and* every `CORELANTIC_API_*` variable, so tests inherited whatever a developer or CI runner had set: some failed for people who followed the setup docs, and the rest passed only because someone's file held the value they asserted. An autouse fixture strips both channels, with canary tests that fail loudly if it ever stops (#48).
- **The fixture mirrors the real schema.** One registry serves both, so a fixture test is a real test. Fixture reproduces the source: 86,973 leads, 38.3% no-geo, voucher rate 24.1%, answer rate 80.86%, agent conversion 4.44%.

## Running it locally

```bash
make install                 # both apps
make dev-api                 # API on :8080  (docs at /docs)
make dev-web                 # web on :3000
make client                  # regenerate the typed API client after API changes
make check                   # lint + typecheck + tests, both apps
make validate                # validate the semantic registry
```

Business API routes are **fail-closed**: set the same secret in both apps or they answer 503. In `apps/api/.env` set `CORELANTIC_API_INTERNAL_API_KEY`, and in `apps/web/.env.local` set `INTERNAL_API_KEY` to the same value. Copy each app's `.env.example` to start.

`CORELANTIC_API_DATA_SOURCE=fixture` needs nothing external. `=azure_sql` needs the ODBC driver, the VPN, and a device-code login on first read.
