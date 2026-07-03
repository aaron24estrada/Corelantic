import "server-only";

import createClient from "openapi-fetch";

import { env } from "@/lib/env";
import type { paths } from "@/lib/api/schema";

// Typed client for the private API, used from Server Components and route handlers.
// It carries the internal secret and never runs in the browser — client components
// reach the API through the BFF proxy (src/app/api/bff) instead.
export const apiServer = createClient<paths>({
  baseUrl: env.apiBaseUrl,
  headers: env.internalApiKey
    ? { "x-internal-api-key": env.internalApiKey }
    : undefined,
});
