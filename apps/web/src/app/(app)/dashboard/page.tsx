import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { apiServer } from "@/lib/api/server";

// Fetched per request from the private API (server-to-server), so it is never
// statically prerendered at build time.
export const dynamic = "force-dynamic";

// What each metric can be asked, in the order a reader cares about it. The catalog computes
// this from the same rules the query engine enforces, so a chip here is a promise the API keeps.
function capabilities(metric: {
  groupable_dimensions: string[];
  supports: { compare: boolean; accumulate: boolean };
}): string[] {
  const count = metric.groupable_dimensions.length;
  return [
    `${count} ${count === 1 ? "dimension" : "dimensions"}`,
    ...(metric.supports.compare ? ["compare"] : []),
    ...(metric.supports.accumulate ? ["running total"] : []),
  ];
}

export default async function DashboardPage() {
  const { data, error } = await apiServer.GET("/api/v1/catalog");

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
                <CardContent>
                  <ul className="flex flex-wrap gap-1.5">
                    {capabilities(metric).map((capability) => (
                      <li
                        key={capability}
                        className="bg-muted text-muted-foreground rounded-full px-2 py-0.5 text-xs font-medium"
                      >
                        {capability}
                      </li>
                    ))}
                  </ul>
                </CardContent>
              </Card>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
