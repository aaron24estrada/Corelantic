# Corelantic MVP — Data Access & Semantic Layer (Draft)

> This is the highest-risk part of the MVP. The dashboard is mechanical; the thing that decides whether the demo lands is whether natural-language questions return *correct* answers. That correctness comes from the semantic layer, not from the model.

## Reading the data

For the MVP we **read KRW's existing Azure SQL directly** — we do not copy, sync, or transform the source. This matches the call ("imagine the centralized Azure SQL is there; start with a single source") and the KRW spec (the app does not own the data).

### Guardrails (non-negotiable)

1. **Read-only, least-privilege credential**, separate from the ETL/writer account. It can `SELECT` from an allowlisted set of tables/views and nothing else.
2. **Prefer a read replica or a set of curated analytic views** over hammering the live OLTP/ETL tables. KRW's Power BI + ThoughtSpot + ETL run against this DB; our ad-hoc analytic queries must not degrade their production. Curated views also give us a stable contract if the underlying schema shifts.
3. **Every query is parameterized, `SELECT`-only, bounded** — enforced statement timeout and a hard row cap on every read.

### Open item: what "Azure SQL Express" actually is

"Azure SQL Express" is not a precise product name. Before we commit the connection strategy we must confirm one of two things. It may be **SQL Server Express** (the free edition, roughly 10 GB per database and 1 GB RAM, running on a VM) — resource-limited and likely the live DB, which makes a replica/views strategy more important. Or it may be **Azure SQL Database** (the managed service, e.g. Serverless or Basic) — easier to read against, but still production. Either way the driver is SQLAlchemy Core (async) over ODBC Driver 18 (`aioodbc`), or `pymssql`. This is tracked as [`decisions.md`](./decisions.md) O-1.

## Why raw text-to-SQL is not enough

ThoughtSpot Spotter feels smart because ThoughtSpot has a **semantic model** — curated worksheets that map business language ("cost per lead", "signed cases") to specific columns, joins, and aggregations. If we point an LLM at raw tables and let it write SQL, we lose that curation: it guesses table names, invents joins, and misdefines metrics. The result is a chat that is *visibly worse* than the ThoughtSpot surface we're replacing — which fails the whole "looks the same or better" test on the chat side.

So the semantic layer is not gold-plating. It is the minimum needed to hit parity.

## The semantic layer

A small, hand-authored registry (YAML in `semantic/`) that defines the business vocabulary behind the nine dashboard visuals and the questions users will ask. It is the **single source of truth** for both request paths (dashboard and NL).

### What it contains

- **Metrics** — a name, definition, aggregation, and the source table/view + expression. e.g. `new_leads`, `signed_cases`, `cost_per_lead` (= `marketing_spend / new_leads`), `marketing_spend`, `lead_to_signed_rate`.
- **Dimensions** — the fields you can group/filter by, with their source columns. e.g. `channel` (Facebook / Google / Referral / Linear TV / Website), `region` (Texas metros), `week`, `month`, `intake_status`.
- **Synonyms** — natural-language aliases per metric/dimension ("spend" → `marketing_spend`, "conversions"/"signings" → `signed_cases`) to improve NL matching.
- **Constraints** — allowed grains, default time window, join rules, row caps.

### Sketch

```yaml
metrics:
  new_leads:
    label: "New leads"
    description: "Count of new intake leads created in the period."
    source: analytics.v_leads          # a curated view, ideally
    expression: "count(*)"
    grain: [week, month]
    synonyms: ["leads", "new intakes"]

  cost_per_lead:
    label: "Cost per lead"
    description: "Marketing spend divided by new leads."
    derived_from: [marketing_spend, new_leads]
    expression: "sum(spend) / nullif(count(distinct lead_id), 0)"
    format: currency
    synonyms: ["CPL", "cost per acquisition"]

dimensions:
  channel:
    label: "Channel"
    source: analytics.v_leads
    column: channel
    members: [Facebook, Google, Referral, "Linear TV", Website]
  region:
    label: "Region"
    source: analytics.v_leads
    column: metro
```

### How each path uses it

- **Dashboard:** each visual references a metric + fixed dimension(s). The compiler turns `metric=new_leads, grain=week` into parameterized SQL. Deterministic, no LLM.
- **NL panel:** the LLM is given the registry (metrics, dimensions, synonyms) and must answer with a **structured query intent** drawn only from it — e.g. `{ metric: cost_per_lead, group_by: channel, grain: month, filter: {region: Houston} }`. The compiler validates every field against the registry and turns it into the same parameterized SQL. **The LLM never emits SQL we run directly.**

### Why structured-intent instead of LLM-authored SQL

- **Safety:** no SQL injection or destructive statements from model output — we compile the SQL ourselves from a closed vocabulary.
- **Correctness:** metric definitions ("cost per lead") are fixed once, by us, not re-derived (often wrongly) per question.
- **Debuggability:** a bad answer is a bad *intent* we can inspect, not opaque SQL.

### Guarded raw-SQL fallback (optional, later)

For questions that don't map to a known metric, we *may* later allow the model to draft SQL — but only against the read-only allowlisted views, validated (SELECT-only, parsed, row/time-capped) before execution, and clearly marked as lower-confidence in the UI. Not required for the MVP; noted so the design leaves room for it.

## What we need from Imran to build this

1. Confirmation of the DB edition and a **read-only credential** (O-1).
2. The **schema** for the tables/views behind those nine visuals — column names, grains, and how the current Power BI / ThoughtSpot metrics are defined, so our semantic-layer definitions match what KRW already sees (O-2). Reusing existing view definitions is ideal.
