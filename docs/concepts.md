# Core Concepts

Three ideas that the whole architecture rests on. They are not obvious from reading the code, and getting them wrong leads to the wrong design (per-visual models, precomputed metric tables, an agent that can't generalize). Read these before working on the semantic layer, the query engine, or the dashboard. They map onto the diagrams in [`diagrams/`](./diagrams/) and the flow in [`architecture.md`](./architecture.md).

## 1. We model definitions, not data

The semantic model is **not** storage and it does **not** compress the wide source into a few small tables. It is a dictionary of **named recipes for querying**. `cost_per_lead` is not a value and not a column — it is the *definition* `spend / leads`. Nothing is precomputed, copied, or materialized.

There are only four *types* — Entity, Dimension, Measure, Metric (hence four classes in `app/semantic`) — but you write **many rows of each**. KRW's model is roughly **one Metric per Power BI measure** (~70), plus ~50 dimensions. So the model is as "wide" as the number of business concepts; it is *definitionally* rich while staying *structurally* small.

Consequences that drive real decisions:

- **Lazy, always fresh.** A metric is computed only when a visual asks, straight from current data. No stale copies, no sync job. This is why the MVP needs no app database — there is no derived data to persist.
- **Combinatorial flexibility.** ~40 measures × ~50 dimensions × filters × grains is thousands of possible queries from a small set of definitions. You define a *vocabulary*; visuals compose *sentences*.
- **Industry-standard shape.** Power BI measures (DAX), LookML, Cube, dbt MetricFlow are all "definitions over a store." We author the same thing in YAML instead of DAX. That is what "Mapping B" is.

The mental correction: the "wide data → few tables" squeeze never happens. Wide data maps to a dictionary that is ~1:1 with business concepts (no compression); the real narrowing happens later, when a single visual selects just a handful of definitions.

## 2. The model is visual-independent

The store and the model know nothing about charts. Only the **intent** is aware a specific request exists, and only the **chart spec** knows it will be drawn as a chart.

```
Canonical store  — knows tables/columns.        No metrics, no charts.
Semantic model   — knows metrics & dimensions.  No charts.            ← visual-independent
────────────────────────────────────────────────────────────────────
Intent           — "leads + spend, by month"    ← first layer aware of a request
Chart spec       — "...draw as bars + lines"     ← the only layer that knows it's a chart
```

The dividing line is between **model** and **intent**: above it is a reusable dictionary of *what can be asked*; below it is *someone asked this, drawn this way*.

Why it matters:

- **One model, N visuals.** `leads` is defined once; the KPI tile, the trend line, the by-channel bar, and an agent's ad-hoc answer all reuse it. No visual "owns" a metric.
- **Change the chart, touch nothing below.** Bubble → scatter, bars → lines, single → dual axis is all chart spec (presentation). The model, the SQL, and the store are untouched. This is exactly why the deterministic and agentic paths share the entire engine and differ only at the top.
- **New visual, usually zero model change.** If the metrics and dimensions it needs already exist, a new tile is just a new intent plus a chart spec.
- **The agent works *because* of this.** It composes intents from the visual-independent vocabulary and never needs to know which charts exist. A visual-specific model could not be driven by an open-ended agent.

Visual-shaped requirements (a funnel needs ordered stages, a time series needs a grain, a map needs geo) are expressed as **intent shape** (`group_by`, `grain`), not baked into the model — so the model stays a neutral vocabulary and the intent adapts it per visual.

The test: delete every visual from the app. The store and the model are unchanged and still valid — you have lost the *questions*, not the *ability to answer them*. That asymmetry is the independence.

## 3. The model is bounded by the schema

Independence from visuals is not independence from the store. A definition can only point at columns that exist: `leads` is definable only because `leads.lead_id` is in the store. So the model is **visual-independent but schema-dependent**, and visuals are bounded by the model, one-directionally.

```
schema  ──bounds──▶  model  ──bounds──▶  visuals
(what exists)      (what's defined)    (what can be shown)
```

This is a *ceiling*, not coupling: the store does not know which metrics exist, and the model does not know which visuals exist. Each lower layer sets the outer limit of the one above without depending on it.

Practical consequences:

- **You cannot visualize what is not modeled, and cannot model what is not in the store.** A missing metric is a few lines of YAML *if the column exists*; a missing column means going back to ingestion (Mapping A), which is far more expensive.
- **So keep the canonical store a little wider than today's visuals need.** Carry columns we are not charting yet. Spare ingredients make new recipes cheap and avoid re-ingestion later. (This also informs the schema work once the real KRW schema lands — see [`data-model.md`](./data-model.md).)
- **Definitions are validated against real columns.** A metric that references a non-existent column fails at load, and the agent's planned intents are checked against the registry before compiling. That validation is exactly what makes the agent's SQL trustworthy instead of hallucinated (the trust boundary in [`data-and-semantic-layer.md`](./data-and-semantic-layer.md)).

## In one sentence

**Mapping A moves and shapes the data; the store is a wide, visual-agnostic set of columns; Mapping B defines — over those columns — a visual-independent vocabulary of how to ask questions; and a single visual is a schema-independent rendering of one intent that selects a handful of those definitions.** Keeping data, definitions, and rendering in separate layers is what lets one model drive both a fixed dashboard and an open-ended agent.
