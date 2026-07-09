import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { apiServer } from "@/lib/api/server";

// Fetched per request from the private API (server-to-server), so it is never
// statically prerendered at build time.
export const dynamic = "force-dynamic";

export default async function DashboardPage() {
  const { data, error } = await apiServer.GET("/api/v1/metrics");

  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-col gap-1">
        <h1 className="text-[28px] font-semibold tracking-tight">
          Executive overview
        </h1>
        <p className="text-muted-foreground text-sm">
          {error
            ? "The metric catalog is unavailable."
            : `${data.metrics.length} metrics defined. The visuals are built on these next.`}
        </p>
      </header>

      {error ? (
        <Card>
          <CardHeader>
            <CardTitle>Can&rsquo;t reach the API</CardTitle>
            <CardDescription>
              Start it with <code>make dev-api</code>, then reload this page.
            </CardDescription>
          </CardHeader>
        </Card>
      ) : data.metrics.length === 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>No metrics defined</CardTitle>
            <CardDescription>
              Add one to the semantic registry, then run{" "}
              <code>make validate</code>.
            </CardDescription>
          </CardHeader>
        </Card>
      ) : (
        <ul className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {data.metrics.map((metric) => (
            <li key={metric.name}>
              <Card className="h-full">
                <CardHeader>
                  <CardTitle>{metric.label}</CardTitle>
                  <CardDescription>{metric.description}</CardDescription>
                </CardHeader>
              </Card>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
