# Status & Handoff

Last updated 2026-07-21. A snapshot of where the build is, what's verified, what's blocked, and what to do next — written so a fresh session can continue without prior context. Decisions and their rationale live in [`decisions.md`](./decisions.md); the real KRW schema lives in [`data-model.md`](./data-model.md); this is the "where are we / what next" view.

## The headline

**There is a review deployment, and the dashboard is a full executive surface.** The stack runs as three containers on an EC2 host at **`98.91.116.58`** behind one nginx entry point with basic auth (#66) — on **sample data**, because the host cannot reach the warehouse yet (#69). As of PR #62 the app is a top-bar executive report — a revenue hero, a KPI stat band, the intake funnel, channel/geo breakdowns, and a **net-new Call Center section** over the telephony registry (Zoom calls + agent performance) that the embedded dashboard never showed. Run locally against `azure_sql` it renders end-to-end on live `gold_tspot` with real figures (~$224M revenue, 130k leads, 28.7% voucher rate, 80.7% answer rate).

**Two gates before live data reaches that host**: TLS (#67 — it serves plaintext HTTP today, so basic-auth credentials cross in the clear) and the access grant (#69).

**The backend serves 26 real metrics** over KRW's live Azure SQL (`gold_tspot`) through `POST /api/v1/query`, and the same registry runs against a seeded fixture that reproduces the source's numbers. Every metric on KRW's Executive Summary is reachable **except Spend and ROAS** — and that gap is an access grant (#37), not code.

One live-data gotcha now handled: SQL Server returns ratio/derived metrics as high-precision decimal **strings** (counts come as numbers), which a `typeof === "number"` guard silently dropped to "—" on Azure while the fixture's SQLite floats hid it. A shared `toNumber` in `lib/format` coerces at every read (value extractors, chart data, tooltips). The Azure dashboard is also **slow and erratic** (12–130s) — connection/token overhead per request plus `stages` distinct-counts; tracked in **#63**, fixture stays instant.

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
  - **`ChartSpec`** — the fourth seam (D-6), authored in the API contract so it flows through OpenAPI into the generated TS client, and built by a pure function of `(chart request, resolved intent, ResultSet)`. It carries its data, so `<Chart>` is a dumb adapter and every pivot decision is under pytest.
- **`apps/web`** (Next.js 16, React 19, Tailwind v4) — typed API client from the OpenAPI schema, BFF boundary, and the **executive dashboard (v3)**. Shell is a translucent top bar over a 1200px report column (sidebar dropped until multi-page + NL land). Charts still route through one `<Chart>` over `echarts/core` (theme in exactly one place, `lib/chart/echarts-option.ts`; single-series lines carry a faint area fill). `/dashboard` now composes: a **revenue Hero** (headline + monthly trend + facts), a hairline-divided **StatBand** (New leads · Voucher rate · Answer rate · Total calls · Agent conv., each a sparkline KPI), the **intake funnel** and ranked **bar lists** (channel/state/dispositions) as custom CSS marks reading the `ResultSet` directly, and the **Call Center** section. Presentational components share `headline`/`scalar`/`categoryRows` helpers (`components/dashboard/headline.ts`); formats always come from the column. Headline figures use self-hosted **Bricolage Grotesque** (`next/font/local`); data-grid numbers stay tabular.

- **Deployment** (#66) — the stack is containerised and running on a review host. `apps/api/Dockerfile` (uv builder → slim runtime carrying `msodbcsql18` + `unixodbc`, so the live switch is config rather than a server yak-shave), `apps/web/Dockerfile` (`output: standalone`, no `node_modules` in the runtime layer), both as uid 10001. `compose.yaml` splits `edge`/`backend` networks — `backend` is deliberately **not** `internal`, because the API needs egress to Entra — caps memory from measurement (fixture seeding peaks at 276MB), and rotates logs. `deploy/bootstrap.sh` is idempotent host prep; `systemctl enable docker` plus `restart: unless-stopped` survives a reboot, so there is no unit of our own.

D2–D5 and the two new dashboard tickets are done: **D7 (#61)** Call Center section and **D8 (#60)** exec visuals landed with PR #62, adding the `funnel_reach` metric (a `stages` measure grouped by `stage_name`, fan-out free). **#14** is re-scoped to the gated remainder only: the **trends combo** (needs spend #37 + index-to-base), the proper **funnel shape** (needs a `FUNNEL` chart type + ordered `stage_name` members — an interim funnel-as-bars ships today), and the **US map** (needs a `MAP` type + US-states geoJSON).

`make check` green: 250 pytest + 31 vitest. `make validate` green: 5 entities, 19 measures, 14 dimensions, 26 metrics, 1 constant across two registry files.

## The review host

`i-02b9f53ce94ba1530` — t3.small, Amazon Linux 2023, us-east-1, Elastic IP **98.91.116.58**, repo cloned to `~/corelantic` via a **read-only deploy key** (enabling it required flipping the org's `deploy_keys_enabled_for_repositories`).

Three containers, one published port: nginx `:80` → `web:3000` → `api:8080`. Verified on the host: **401 unauthenticated / 200 authenticated**, `:8080` and `:3000` refused from outside, and 600MB of 1913MB in use with swap untouched even through the Next build.

Deploying is `git pull && docker compose up -d --build`. Switching to live data is an `.env` edit (`CORELANTIC_API_DATA_SOURCE=azure_sql` plus the service-principal credentials) and `docker compose up -d` — no rebuild — but **not before #67 and #69**.

Two things about it that will bite if forgotten: SSH is scoped to a single IP that is currently the **KRW VPN egress**, so dropping the VPN loses SSH until the security group is updated; and port 80 is open to the world (#68).

## The API in one page

Four routes. `/health` is open; the rest need the internal secret (`x-internal-api-key`).

**`GET /api/v1/catalog`** — the vocabulary, and what may be asked of it. Read it before composing an intent. Per metric: `groupable_dimensions` (valid for `group_by` *and* `filters`), `date_dimensions`, and `supports: {compare, accumulate}`. Per dimension: `members`, when the value set is closed. Plus `grains`, `relative_ranges`, and `accumulation_resets` — the calendar rule saying which resets each grain may use.

It bounds the **vocabulary**, not the *shape* of a request. Three refusals remain reachable from catalog-only names, because each is a property of the question: `compare` with `accumulate`, grouping by the very date `grain` buckets, and a running total starting mid-period.

**`POST /api/v1/query`** — an intent in, a `ResultSet` out, and a `ChartSpec` too if you ask for one.

```jsonc
// request — `chart` is a sibling of the intent, never a field on it
{
  "intent": {"metric": "voucher_rate", "grain": "week", "compare": {}, "date_range": "last_90_days"},
  "chart": {"type": "line"}          // omit for rows only
}

// response
{
  "result": {
    "columns": [
      {"name": "period",       "role": "period",   "label": "Period"},
      {"name": "voucher_rate", "role": "metric",   "label": "Voucher rate %", "format": "percent"},
      {"name": "previous",     "role": "previous", "label": "Previous voucher rate %", "format": "percent"},
      {"name": "delta",        "role": "delta",    "label": "Change", "format": "percent_point"}
    ],
    "rows": [{"period": "2026-07-06", "voucher_rate": 0.2717, "previous": 0.2558, "delta": 0.0159}],
    "resolved_intent": {"date_range": {"start": "2026-04-12", "end": "2026-07-10"}, "compare": {"kind": "change"}, /* … */}
  },
  "chart": {
    "type": "line", "title": "Voucher rate %", "subtitle": "12 Apr 2026 – 10 Jul 2026",
    "categories": ["2026-07-06"],
    "series": [
      {"name": "Voucher rate %", "data": [0.2717], "role": "primary",    "palette_index": 0, "format": "percent"},
      {"name": "Previous voucher rate %", "data": [0.2558], "role": "comparison", "palette_index": 0, "format": "percent"}
    ]
  }
}
```

`chart` is deliberately **outside** the intent: an intent is a question and is visual-independent, so `resolved_intent` never echoes a chart type back and E2's planner never has to choose a visual in order to ask anything.

Three things that shape the frontend:

- **`columns` describes the rows.** Roles and formats come from the API, so a chart, a table and a narrative all read one description. Never re-derive them from the intent.
- **`resolved_intent` is the request as actually run** — relative window turned into explicit dates, inferred date dimension named, comparison's `kind` decided. A caption can state the window the chart truly covers.
- **`delta` of a percent metric is in points, not percent.** 20% → 24% rose four points. The API picks that from the metric's format and says so via `format: "percent_point"`.

**Every bad intent is a 422**, never a 404 or a 500, with a stable `code`, the `field` at fault, and `allowed` — the vocabulary that *would* have worked:

```json
{"code": "incompatible_dimension", "field": "group_by",
 "detail": "Metric 'voucher_rate' cannot be sliced by dimension 'stage_name': the metric's own measure already filters on that column, so every other group would aggregate to nothing.",
 "allowed": ["channel", "lead_date", "state", "status"]}
```

That `allowed` list is the point: the agent repairs its intent instead of retrying blind (E2), and `ErrorState` names the options instead of saying "failed" (D2).

**Every 422 now wears that one body**, including the ones pydantic raises before a handler runs. FastAPI's own validation error is a *list* of pydantic errors, which was a second shape on the status code that already carried ours — so the client had to narrow `detail` before it could show anything, and `allowed` was not in the generated TypeScript at all. A `RequestValidationError` handler normalises it, and the routes declare `422: ErrorResponse`.

A `ChartSpec` cannot always be drawn from a result, so two more codes exist. Both are chart-request faults, reported against `chart` or `group_by` and never against the intent:

- `unsupported_chart_type` — a `line` with no grain to run along; a `bar` with both a period and a group. `allowed` names the types that would have worked.
- `unpivotable_dimension` — splitting a trend into one series per member requires each member to hold a colour that a filter cannot move (below). `channel` declares nine members and there are eight colours; `state` declares none at all.

**`POST /api/v1/nlq/ask`** — question in, the same `ResultSet` plus a narrative, and a `chart` slot that E3 fills. Blocked on E1.

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
- **Revenue is not stored**: Power BI computes it as `vouchers × $6,000`. That fee is a registry constant (`case_fee`), confirmed current by Imran on 2026-07-14.

## Blocked — the real critical path

- **Spend + Referrals (#37) — the only thing between us and the full dashboard.** `marketing_budget` (spend → **ROAS**, **Cost per Lead**) and `referral_leads` (cancer type, referral firm, fees) are **not in `gold_tspot`**. The `bronze_marketing`, `bronze_finance`, and `*_lawruler` schemas exist in the same database but this login cannot read them. Both originate as spreadsheets landed into the warehouse, so this is most likely an access grant, not a connector. Owner: **Imran**.
- **#69 — the review host cannot reach the warehouse.** Two asks of **Imran**, both independent of #37: allow-list the host's Elastic IP `98.91.116.58` on the Azure SQL firewall, and provide a read-only **service principal** on `gold_tspot` (tenant/client id + secret). Deployed auth cannot be device-code — a container has no one to answer an MFA prompt. The code path and compose variables already exist; only the credentials are missing.
- **#67 — TLS, before live data goes anywhere near that host.** It serves plaintext HTTP, so the basic-auth credentials and every byte of the dashboard cross in the clear. Blocked on a DNS name: Let's Encrypt will not issue for a bare IP.
- **O-4 — auth.** Reuse Entra vs. Corelantic's own IdP. Owner: you/Dom. Blocks the web login.
- **E1 — Anthropic API key.** Blocks the NL agent (the planner can be built and tested against a fake).
- **O-3 — deploy target** (Azure vs GCP). Parked for Dom; not blocking.
- **#63 — live Azure SQL is slow & erratic (12–130s).** Per-request connection/token overhead plus `stages` distinct-counts; even a bare `COUNT` has taken 65s cold. Not blocking (fixture is instant) but it undercuts a live demo. Owners: us (pool warming, dashboard concurrency, caching slow-moving scalars) + Imran/KRW (warehouse indexing / gold-layer pre-agg).

**O-5 is resolved (2026-07-10): Apache ECharts.** We stopped waiting for Imran to confirm his agent's format, because waiting inverted D-6 — `ChartSpec` is a seam *we* own, and a differently-shaped agent output is an adapter at the boundary, not a redesign. D3 and D6 are unblocked; the reasoning is in [`decisions.md`](./decisions.md), D-8.

## Next steps

Unblocked, highest value first (the dashboard is now largely done — the frontier is the agent and live-readiness):

0. **#68 — narrow port 80 to the reviewers' IPs.** Minutes of work, and the only thing standing in front of the host today is plaintext basic auth. Do this while the review is running.

1. **E2 — `plan_intent`** (question → validated intent), buildable against the `LLMProvider` interface with a fake, run against the fixture. `GET /catalog` gives the planner its vocabulary; the 422 body's `allowed` list lets it repair a bad intent instead of retrying blind. Needs no API key. **Note the pivot in [`decisions.md`](./decisions.md): NLQ is proposed to lean on ThoughtSpot first (pending Dom), which would re-scope epic E; confirm before investing heavily in the in-house planner.**
2. **#63 — live Azure SQL perf.** The dashboard is verified correct on `gold_tspot` but slow/erratic; pool warming + fewer/batched dashboard queries + a small cache for all-time scalars would make a live demo snappy. Fixture is the fast path meanwhile.
3. **#14 remainder — the funnel *shape* and the US map.** The funnel already ships as bars; the tapered `FUNNEL` shape and the `MAP` are new `ChartType`s (extend `ChartSpec`, register in `components/chart.tsx`, do **not** add a bespoke component). `FUNNEL` also needs `stage_name` to declare its members in order; the map needs a US-states geoJSON asset. The trends combo still waits on spend (#37).
4. **A1 — CI running `make check` on PRs.** CI will need `msodbcsql18` + `unixodbc-dev` to build `pyodbc`. The suite is hermetic now (#48): it ignores `.env` and every `CORELANTIC_API_*` variable, so CI can set whatever it likes.
5. **#53 / #52 — partial-bucket family.** `accumulate` vs display window (#53) and `compare`'s `LAG` skipping empty periods (#52); fix before the D6 date-range control lands.
6. **#72 — component tests.** A cleanup pass dropped the zero guards in `bar-list` and `funnel`, rendering `NaN%` and `Infinity%`, and **`make check` stayed green**: a review caught it, not the suite. `apps/web` has no component tests at all.
7. **#70 — vendor Open Sans**, so image builds stop depending on Google Fonts. **#71 — build off-box (ECR + instance role)**, which removes the GitHub credential, the build cache and the build-memory constraint from the host in one move.

Gated: spend/referrals registry (#37), live data on the host (#69), TLS (#67), NL agent wiring (E1), auth (O-4).

## Traps to know in the dashboard

Read these before touching `apps/web`.

1. **A series' colour belongs to the entity, not to its position.** `--chart-1..8` in `apps/web/src/app/globals.css` are now eight validated hues in both modes (the five greys are gone). `ChartSpec.series[].palette_index` is the member's index in the registry's **declared `members`**, so cross-filtering a trend down to two channels leaves those two the colour they already were. Index the palette by array position instead and a filter silently repaints the survivors — the reader re-learns the legend without noticing.

   The consequence, which surprises people: **a dimension can only be pivoted if it declares a closed member list of ≤ 8.** Today that is `call_direction` (2) and `call_result` (7). `channel` declares **nine** members and `state` declares none, so neither can split a trend — `POST /query` answers `422 unpivotable_dimension`. Nominal bars are unaffected (`leads by channel` is one series, every bar in slot 1 — colouring bars by their value would spend the identity channel re-encoding what bar length already shows). Folding a ninth member into "Other" is the obvious fix and is **not** trivial: `channel` already has members literally named `Other`, `Unknown` and `Other Social Media`, so a synthesised bucket would collide with a real one and quietly change the numbers. It needs the registry to mark a residual member. Filed as **#58**, not built.
2. **SQL Server sends decimals as strings; coerce every numeric read.** Ratio and derived metrics (voucher/answer/agent-conversion rates, revenue, percent deltas) come back as high-precision decimal **strings** on Azure, counts as numbers. A `typeof === "number"` guard silently drops the strings to null → "—" on live data, invisible in dev because the fixture's SQLite returns floats. Read cell values through `toNumber` (`lib/format`) — it is already wired into the value extractors, chart series data and tooltips. The KPI row is now a **StatBand** (5 live tiles, no placeholders); Spend/ROAS are noted in the page footer, not faked, until #37.
3. **A KPI tile is one request, not two.** `POST /query` with `grain` + `compare` returns `period`, the value, `previous` and `delta` together, over one window. Do not fetch a metric and its delta separately; that was the old design and it could not guarantee both covered the same days.
4. **The KPI headline is the last weekly bucket, which is a *partial* current week.** So early in the week every tile reads low and its WoW delta looks like a crash (leads 473 → 265, −44%, because the week is two days old). Filed as **#59**, alongside the partial-bucket family (#52/#53), and the honest fix is API-side: a "last complete period" the headline can point at. Do not paper over it with week-boundary math in the view layer — that duplicates the compiler's calendar and will drift from it.

"Recent intakes" (D5) is the one visual with no metric behind it — it wants raw rows, not an aggregate, and no endpoint returns those.

## Working agreements that paid off

- **Probe the database before authoring a metric.** Three definitions that looked obvious from column names were wrong by 4×, 1000×, and 2×. The probes cost minutes; the errors would have been invisible on a dashboard.
- **Run a codex architectural pass on every PR — and on the *plan*, before writing code.** Reviewing the plan for the semantic-API rework caught a sequencing bug (flipping `SemanticError` to 500 while a route still raised it from a path param) and a filtered-measure case we had missed, before either existed as a diff. Reviewing diffs has caught eight bugs that would have shipped silently: a Sunday-boundary week bucket in SQL Server, `LAG` reading across a NULL period, a registry constant shadowing a measure, a derived formula selecting an unaggregated literal, a dark-mode focus ring that vanished while a button was held down, a running total that started mid-period under the same label as an honest one, a derived metric that could declare itself additive while dividing by a measure, and — in the chart builder — a label-keyed pivot that silently dropped a bar when a NULL and a literal `"(Blank)"` shared a column, losing part of the total on a chart nobody would think to distrust. The fix (align by row position, never by display label) also caught that the offending dict was doing no work the row order didn't already carry.

  Redirect stdin or it hangs forever on `Reading additional input from stdin...`, and never pipe it through `tail` — `tail` buffers until the stream closes, so a hung run and a working one look identical:

  ```bash
  codex exec --sandbox read-only --skip-git-repo-check "$(cat prompt.txt)" < /dev/null > codex.log 2>&1
  ```

  Two shell traps around it: `pkill -f "codex exec"` matches the agent's own shell and kills the session — `kill` by PID. And a triple-backtick fence inside `$(cat <<'EOF')` unbalances bash's legacy backtick parsing, so `gh issue create --body-file` beats `--body "$(…)"`.
- **Compute the palette; never eyeball it.** The `dataviz` skill ships a validator, and it earns its keep immediately: `#0a9a24` reads as a clean green beside the yellow and scores **ΔE 1.4** under protanopia — the two collapse into one line. The eight hues were derived, not chosen: seed slot 1 with `--primary`, snap the three sub-3:1 hues darker *in-hue* against our own white card (not the reference's off-white surface), then enumerate all 5040 slot orderings and keep the one maximising the worst adjacent ΔE across **both** modes. Result: 4/4 checks pass in each mode, worst adjacent ΔE 23.5 / 23.7 against a target of 12. Two traps on the way: darkening the yellow for contrast collapsed green↔yellow to 9.4 until the order changed, and six of the eight dark-mode contrast ratios I first wrote from memory into the CSS comment were wrong. Measure, then write the number down.

- **Render the thing, not the object you meant to render.** ECharts draws to an SVG string in Node (`echarts.init(null, null, {ssr: true, renderer: "svg"})`), so the renderer is testable with no browser and no canvas. Asserting on the option object said the adapter was correct; actually drawing it said `grid.containLabel` is **deprecated and inert in ECharts 6** — the chart still drew, and merely clipped its own axis labels. A deprecated option is never an exception; it is a log line and a subtly wrong picture.

- **Probe with a value that changes behaviour.** The hermetic-tests fix (#48) looked complete under `.env`, which only sets `data_source=fixture` — something the tests tolerate. Exporting `CORELANTIC_API_SEMANTIC_DIR=/tmp/nope` turned 24 tests red and exposed a fixture-ordering bug (pytest builds module-scoped fixtures before function-scoped autouse ones). A probe that cannot fail proves nothing.

  It bit again immediately. The test guarding against deprecated ECharts options spied on `console` *inside* the test — but ECharts logs each deprecation once per process, and an earlier chart in the same file had already spent it, so the guard passed with `containLabel` restored. Moving the spy to `beforeAll`, ahead of the first draw, made it fail. **Re-introduce the bug and watch the test go red**, every time: three assertions in this PR (the palette-slot contract, the comparison hue, this one) were confirmed that way, and only one of the three was already correct.
- **Verify a claim numerically before building on it.** The whole intent-modifier redesign rested on "a ratio can be recomputed per bucket and then compared." That was checked against 185 weekly buckets of a hand-computed series *before* any code was written, and the check is now a test. The per-bucket mean (0.2414) differs from the whole-period ratio (0.2434) — which is the proof it is a genuine recomputation and not a reweighting, and the same mean-of-ratios trap [`data-model.md`](./data-model.md) records for `agent_stats`.
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
