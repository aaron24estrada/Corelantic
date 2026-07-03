# Next.js / TypeScript Standards

Applies to `apps/web`. Read [principles.md](principles.md) first. Next.js App Router, React Server Components, TypeScript strict, Tailwind, ECharts, Auth.js.

## Rendering model

- Server Components by default. Add `"use client"` only for genuine interactivity (state, effects, event handlers, browser APIs). Keep client components small and at the leaves of the tree.
- Fetch data and read secrets on the server. The browser talks only to our app. Service keys, database credentials, and tokens never reach the client.
- Use server actions or route handlers for mutations and auth. Keep them thin, validate input, and delegate to `lib`.

## The BFF boundary

- The browser talks only to the web app; the web app calls the FastAPI service server-to-server. This mirrors the KRW pattern and is not optional.
- The internal API is never reachable from the browser. Requests to it carry the internal secret and are made only from server code.
- Derive user identity from the session on the server, never from a client-supplied value.

## Layout

```
src/
  app/         routes (page.tsx, layout.tsx, route.ts) and route-only UI
  components/  shared, reusable UI
  lib/         clients, helpers, non-UI logic (api client, formatting, chart adapters)
  auth.ts      Auth.js configuration
```

- No business logic in components. Extract it to `lib/`.
- Co-locate a component with its route when it is used only there. Promote it to `components/` when it is shared.

## Components

- One component per file as a rule. PascalCase component names. Route files use Next's required names.
- Small and composable. If a component handles layout, data, and logic at once, split it.
- Props are explicitly typed. Prefer discriminated unions over boolean flags for variants.
- Named exports for shared components. Default export only where Next requires it (route files).

## Charts

- Every chart — a dashboard visual or an agent answer — renders through one shared `<Chart>` component that takes a single chart-spec shape. Do not hand-roll a bespoke ECharts config per visual.
- The chart-spec is the contract between backend and frontend and between the dashboard and the agent. Keep its type shared with, or derived from, the API contract. A new visual type means extending the spec, not adding a one-off component.
- Theme is applied in one place (the `<Chart>` wrapper), so every chart looks like the same product. No per-chart color or font overrides.

## Types

- TypeScript strict. `tsc` must pass. No `any`, and no non-null `!` without a justified reason next to it.
- Type external data at the boundary. Prefer the client generated from the backend's OpenAPI schema over hand-written response types. Do not assume the shape of an API response.
- Derive types (`ReturnType`, `Parameters`, `satisfies`) instead of restating them.

## Naming and files

- Files are kebab-case (`confidence-gauge.tsx`), except Next's reserved names.
- Components PascalCase, functions camelCase, true constants UPPER_SNAKE.
- Names describe role: `KpiTile`, `AskYourDataPanel`, not `Component1`.

## Styling

- Tailwind utilities. Keep class lists readable and ordered (layout, spacing, color, state).
- Repeated visual patterns become a component, not a copy-pasted class string. Avoid `@apply` soup.
- Use the theme tokens (colors, spacing, fonts). No one-off hex values when a token exists. Keep the light and dark treatment consistent.

## Data and state

- Prefer server data fetching over client `useEffect`. Reach for client state only for real interactivity (cross-filtering, the chat panel, streaming responses).
- Handle loading, empty, and error states explicitly for every data surface. No blank screens, and no infinite skeletons on failure — render an error state with a retry.
- Invalidate cached data after a mutation so the UI does not show stale results.

## Auth

- Gate protected routes with the session check in the server component and redirect when there is no session. Do not rely on client-side checks for protection.
- Never trust the client for identity or authorization. Identity comes from the Entra session on the server.

## Environment

- Only `NEXT_PUBLIC_` variables reach the browser. Never put a secret in a `NEXT_PUBLIC_` variable.
- Server-only secrets stay in server modules (mark them `server-only`). Do not import them into client components.

## Hygiene

- `eslint` and `tsc` must pass. Do not disable rules without a written reason.
- No dead components, unused props, or leftover template code. Delete the create-next-app boilerplate you replace.
