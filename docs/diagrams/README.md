# Diagrams

Architecture diagrams as D2 source (`.d2`), compiled to `.svg`. ELK layout is pinned inside each file, so `d2 <file>.d2 <file>.svg` reproduces them. Grounded in the KRW Revenue Intelligence Dashboard.

## The set

Small, self-contained diagrams — read `01` first, then zoom in:

| Diagram | What it shows |
| --- | --- |
| [01 · overview](01-overview.svg) | The pipeline, source → visual, as eight stages (the map) |
| [02 · ingestion](02-ingestion.svg) | Mapping A — heterogeneous sources normalize into one canonical store |
| [03 · canonical-store](03-canonical-store.svg) | The per-tenant Postgres schema (small star schema, PK/FK) |
| [04 · semantic-model](04-semantic-model.svg) | Mapping B — the in-house model (Entity/Dimension/Measure/Metric) and how it binds columns |
| [05 · query-engine](05-query-engine.svg) | Intent → compiler (SQLAlchemy Core) → read-only SQL → rows (the trust boundary) |
| [06 · two-paths](06-two-paths.svg) | Deterministic dashboard path vs. agentic path, sharing the engine |
| [07 · api-bff](07-api-bff.svg) | The BFF boundary — browser → web → private API with the internal secret |
| [08 · visual-to-intent](08-visual-to-intent.svg) | A visual is a query shape: each dashboard tile maps to one intent |

[`data-flow.svg`](data-flow.svg) is the single combined diagram (all layers in one); the numbered set is the same content split for readability.

## Regenerate

```bash
# one file
d2 03-canonical-store.d2 03-canonical-store.svg

# all of them
for f in *.d2; do d2 "$f" "${f%.d2}.svg"; done
```

Requires [`d2`](https://d2lang.com).
