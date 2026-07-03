# Principles (apply everywhere)

## Mindset

- Write for the next reader. Clarity beats cleverness.
- Solve the real problem. No hacks, patches, or workarounds. If you reach for one to move forward, stop and fix the root cause, or surface the blocker. A "temporary" workaround is debt that outlives the person who wrote it.
- Prefer the simple, boring solution. Add complexity only when a real requirement forces it. No speculative abstraction for needs that do not exist yet.
- Consistency with the surrounding code and these standards beats personal taste.
- We are building a product to escape lock-in, not another one-off. Depend on our own interfaces, never directly on a vendor's SDK or a specific model from deep in the code.

## Naming

- Names describe intent and domain, not mechanics. `metric_intent`, not `data2`.
- Avoid vague names (`data`, `info`, `manager`, `helper`, `util`, `temp`, `handle`) unless they are genuinely accurate.
- Booleans read as assertions: `is_active`, `has_access`, `should_retry`.
- Functions are verbs, variables and classes are nouns.
- Spell things out. Avoid abbreviations except widely understood ones (`id`, `url`, `sql`).
- Same concept, same name everywhere. A thing is a `metric` or a `dimension` in the docs, the semantic layer, the API, and the UI — do not rename it per layer.

## Comments

- Code says what, comments say why. Never write a comment that restates the code. Avoid `# increment counter` above `counter += 1`.
- A comment earns its place when it records a non-obvious constraint, the reason behind a choice, a link to a spec or issue, or a known gotcha or edge case.
- Prefer making the code self-explanatory (better names, smaller functions) over adding a comment to explain it.
- Module and function docstrings are for orientation and context beyond the signature, not ceremony. If a one-line docstring only repeats the name, drop it.
- No commented-out code. Delete it, git remembers. No `TODO` without an owner or an issue reference. No banner comments or code-narration.

## Structure

- One responsibility per function, module, and file. If you need "and" to describe it, split it.
- Keep functions short and flat. Return early, avoid deep nesting.
- No magic numbers or strings. Name them as constants or config.
- Separate pure logic from IO where practical. A metric definition, an RRF merge, or a confidence calculation should be a pure function you can test without a database or a network.
- No dead code, unused exports, or leftover scaffolding.

## Modularity and boundaries

This is the section that matters most for this codebase.

- **Depend on interfaces, not implementations.** Anything we want to swap — the data source, the LLM provider, the identity provider, the chart format — sits behind an interface we own. Application code depends on the interface; a factory chooses the implementation from config. Adding a second implementation must not touch a single call site.
- **One-way dependency flow.** Higher layers depend on lower ones, never the reverse: `routes → services → (semantic / query / adapters)`. UI concerns do not leak down; data-access concerns do not leak up. No import cycles.
- **A module has one reason to change.** The Azure SQL adapter changes when the connection details change, not when a metric is redefined. The semantic layer changes when the business vocabulary changes, not when the agent's prompt changes.
- **Keep the public surface small.** Export the interface and the entry points, nothing else. Internal helpers stay private to the module.
- **No vendor names in business logic.** `llm.complete(...)`, not `anthropic.messages.create(...)` scattered through a service. The vendor lives in exactly one adapter.

## Trust boundaries (product-specific, non-negotiable)

- **The database is read-only and least-privilege.** Application code reaches the source data through the data-source interface using a read-only account, against an allowlisted set of tables or views. No writer credentials, ever.
- **The model plans; it does not execute.** An LLM may choose *what* to ask from the semantic layer's closed vocabulary and emit a validated structured intent. It must never hand us SQL (or any code) that we run directly. We compile SQL ourselves from validated fields. See [fastapi.md](fastapi.md).
- **Model and user output is untrusted input.** Narratives, summaries, and any generated text are escaped when rendered and never interpolated into SQL, shell, or markup. Ground narratives strictly in query results — a narrative may not state a number the query did not return.
- **Secrets never reach source control, logs, or the client bundle.** All configuration comes from the environment through a typed settings layer. No hardcoded hosts, keys, or magic config values in code.

## Errors

- Fail loudly and early. Validate inputs at the boundary.
- Never swallow errors silently. No empty `except` or `catch`. Handle it, or let it propagate with context.
- Raise specific, meaningful errors. Do not catch broad exceptions to hide problems.
- User-facing error messages are actionable and never leak internals or secrets.

## Types

- Type everything. Avoid `Any` / `any`. Use precise types, enums for closed sets, and explicit types for ids.
- The type checker (`mypy --strict`, `tsc` strict) must pass. No ignore directives without a one-line reason next to them.
- Type external data at the boundary. Never assume the shape of a database row or an API response; validate or type it explicitly.

## Tests

- Test behavior and contracts, not implementation details.
- Pure logic (semantic-layer compilation, chart-spec building, any scoring or merge) is unit-tested without IO.
- Name tests by what they assert: `test_cost_per_lead_compiles_to_expected_sql`.
- Arrange, act, assert. One reason to fail per test.

## Tooling and hygiene

- Linters and formatters are the source of truth for style. Do not fight them or disable rules without a written reason.
- Small, focused commits with semantic messages.
- Add only dependencies you use, and declare them in the manifest.
