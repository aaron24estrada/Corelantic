import "server-only";

// Server-only configuration. These values are read on the server and must never reach
// the client bundle — importing this module from a client component is a build error.
export const env = {
  // Origin of the private API. The BFF calls it server-to-server; the browser never does.
  apiBaseUrl: process.env.API_BASE_URL ?? "http://127.0.0.1:8080",
  // Shared secret presented to the private API. Empty in local dev until provisioned.
  internalApiKey: process.env.INTERNAL_API_KEY ?? "",
} as const;
