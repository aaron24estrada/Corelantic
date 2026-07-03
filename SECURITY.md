# Security

Corelantic reads a client's business data and mediates it through an LLM. A few rules are non-negotiable and predate any code. They exist because this class of app fails in predictable ways; the standards in [`standards/principles.md`](standards/principles.md) reference these.

## Secrets

Real secrets never enter the repository — not in source, not in config, not in commit history, not in logs. Each app ships a `.env.example` with **placeholder** values documenting the variables it needs; the real `.env` is git-ignored and lives only on the machine that runs the app. If a secret is ever committed or pasted into a shared surface, treat it as compromised and rotate it immediately. (The predecessor project had live credentials sitting in its working tree — this file is the guard against a repeat.)

## Database access

The source database is read with a **read-only, least-privilege** account, distinct from any ETL or writer account, scoped to an allowlisted set of tables or views. The application never holds write credentials to the source. Every query is parameterized, `SELECT`-only, and bounded by a statement timeout and a row cap.

## The model plans, it never executes

An LLM may choose what to ask from the semantic layer's closed vocabulary and emit a validated structured intent. It must never hand us SQL, shell, or any code that we run directly — we compile SQL ourselves from validated fields. Model and user output is untrusted input: it is escaped when rendered and never interpolated into SQL or markup, and generated narratives are grounded strictly in query results.

## Trust boundary

The browser talks only to the web app; the web app calls the internal API server-to-server behind a shared secret. The internal API is never reachable from the browser, and user identity is derived from the server-side session, never from a client-supplied value. Secrets and tokens never reach the client bundle.

## Reporting

Found a vulnerability or a leaked secret? Do not open a public issue. Contact the maintainers directly and rotate anything exposed.
