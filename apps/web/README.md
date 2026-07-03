# Corelantic — Web

Next.js (App Router) front end for the Corelantic MVP: the branded shell, the executive dashboard, and the "Ask your data" panel. It owns the user session and acts as a backend-for-frontend — the browser talks only to this app, which calls the private API server-to-server. Read [`../../standards/nextjs.md`](../../standards/nextjs.md) before changing it.

## Stack

Next.js 16 (App Router, React Server Components) · React 19 · TypeScript (strict) · Tailwind v4. The React Compiler is on (`reactCompiler: true`).

## Getting started

```bash
cp .env.example .env.local
npm install
npm run dev            # http://localhost:3000
```

Or from the repo root: `make install`, then `make dev-web`.

## Checks

```bash
npm run lint
npm run typecheck
npm run format
```

`make check` (repo root) runs lint + typecheck + tests across both apps.

## Current state

A minimal, runnable skeleton: layout, a placeholder landing page, and the Tailwind theme foundation. Deliberately not here yet — added in later steps:

- The app shell, navigation, and full Corelantic brand theme (shadcn tokens).
- The typed API client generated from the backend's OpenAPI schema, and the BFF route handlers.
- The dashboard visuals and the NL analytics panel.
- **Auth wiring** — the identity provider is the one pluggable step, pending the reuse-Entra-vs-own-IdP decision (docs O-4).
