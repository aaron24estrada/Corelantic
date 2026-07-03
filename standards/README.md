# Engineering Standards

These are the rules for writing code in this repository. They exist to keep the codebase clear, semantic, and modular, and to keep low-quality or machine-generated slop out. Treat them as rules, not suggestions: code that violates them should not merge.

- [principles.md](principles.md): cross-cutting rules that apply everywhere — naming, comments, structure, modularity and boundaries, errors, types, and the trust boundaries specific to this product.
- [fastapi.md](fastapi.md): backend rules (FastAPI, Python, uv, Pydantic), plus the rules for provider interfaces, data-source access, the semantic layer, and the agent.
- [nextjs.md](nextjs.md): frontend rules (Next.js App Router, TypeScript, Tailwind, ECharts, the BFF boundary).

## How to use them

- Read the relevant file before writing or reviewing code in that area. Do not inline them into context preemptively; open the one you need when you need it.
- Reviewers check changes against these rules. Passing the tools is the floor, not the goal.
- The mechanical parts are enforced by tooling: `ruff`, `mypy --strict`, `eslint`, `tsc`. Run `make check` before committing.

## Why these exist here specifically

Corelantic is a product, not a one-off. The whole reason we are building custom (see [`../docs/spec.md`](../docs/spec.md)) is to own the stack and avoid vendor lock-in — so the standards lean hard on **modularity and boundaries**: swappable seams for anything we do not want to be married to (data source, model provider, identity), a one-way dependency flow, and hard trust boundaries around SQL and untrusted model output. Get those right and the rest is ordinary clean code.
