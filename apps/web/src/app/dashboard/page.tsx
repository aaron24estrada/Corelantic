import { apiServer } from "@/lib/api/server";

// Fetched per request from the private API (server-to-server), so it is never
// statically prerendered at build time.
export const dynamic = "force-dynamic";

export default async function DashboardPage() {
  const { data, error } = await apiServer.GET("/api/v1/metrics");

  return (
    <main className="mx-auto flex min-h-dvh max-w-2xl flex-col gap-6 px-6 py-16">
      <header className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
        <p className="text-muted-foreground text-sm">
          Metric catalog from the API — the visuals are built on these next.
        </p>
      </header>

      {error ? (
        <p className="border-border rounded-lg border p-4 text-sm">
          Could not reach the API. Start it with <code>make dev-api</code>, then
          reload.
        </p>
      ) : data.metrics.length === 0 ? (
        <p className="text-muted-foreground text-sm">No metrics defined yet.</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {data.metrics.map((metric) => (
            <li
              key={metric.name}
              className="border-border rounded-lg border p-4"
            >
              <div className="font-medium">{metric.label}</div>
              <div className="text-muted-foreground text-sm">
                {metric.description}
              </div>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
