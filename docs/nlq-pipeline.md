# Corelantic MVP — NL Analytics Pipeline (Draft)

This describes the agentic natural-language flow that replaces embedded ThoughtSpot Spotter. It is the "Ask your data" panel: a user types a question and gets back a single generated chart and a short narrative grounded in the query result. It runs in-process inside the FastAPI backend — one orchestrator, not a mesh of separate agent services — while keeping full multi-model capability.

## The flow

A question moves through five steps. First, **plan**: the orchestrator, given the semantic registry (metrics, dimensions, synonyms), interprets the question and decides which metric(s), dimension(s), filters, and time grain are needed. Second, **emit a structured query intent**: the model's output is a validated object drawn only from the registry — for example `{ metric: cost_per_lead, group_by: channel, grain: month }` — never raw SQL. Third, **compile and execute**: the query compiler turns that intent into parameterized, read-only SQL and runs it against Azure SQL under a statement timeout and row cap. Fourth, **shape the result**: the chart service turns rows into an ECharts spec (the same spec shape the dashboard uses), and the model writes a one-to-two-sentence narrative grounded strictly in those rows. Fifth, **stream**: the chart and narrative stream back to the panel over SSE so it feels responsive, the way Spotter does.

## Why the model plans but never writes the SQL we run

The model chooses *what to ask* from a closed vocabulary; it does not hand us SQL to execute blindly. This buys three things at once. It is safe — there is no path for model output to inject or run arbitrary or destructive SQL, because we compile the statement ourselves from validated fields. It is correct — a metric like "cost per lead" is defined once, by us, in the semantic layer, rather than re-derived (often wrongly) on every question. And it is debuggable — when an answer is wrong, we inspect a structured intent, not opaque generated SQL. The rationale for this over raw text-to-SQL is covered in [`data-and-semantic-layer.md`](./data-and-semantic-layer.md); the short version is that raw text-to-SQL is exactly where NL quality falls below the ThoughtSpot surface we're replacing.

## Orchestration and models

The orchestrator sits behind the `LLMProvider` interface with Claude as the default. Because everything is custom, the orchestrator can route different steps to different models: a cheap, fast model (or a small language model) for intent planning and narrative writing, and a stronger model only when a question genuinely needs it. This is the model-fragmentation and parallelization Imran wants — it just lives in one process for the MVP. None of it is required for a working first cut; the seam is what matters now, so we ship with a single provider and add routing without touching the app.

## Grounding and trust

The narrative is written only from the returned rows, never from the model's prior knowledge, so it cannot state a number the query did not produce. The chart renders the same rows. If a question does not map to any known metric or dimension, the panel says so plainly and, where useful, suggests the nearest supported question, rather than guessing. Human-in-the-loop, richer report generation, and saved history are deliberately out of this cut; the pipeline is built so they attach later without rework.

## What this cut does not include

No add-to-dashboard (persisting a generated chart), no report or slide-deck generation, no personalization or per-user RAG, and no chat history. Each of these is a later tool or surface hung off the same orchestrator and the same chart-spec contract, which is why the MVP invests in getting those two foundations right rather than in breadth.
