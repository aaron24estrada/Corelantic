import { Chart } from "@/components/chart";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import type { components } from "@/lib/api/schema";
import { apiServer } from "@/lib/api/server";

type CatalogMetric = components["schemas"]["CatalogMetric"];

// Fetched per request from the private API (server-to-server), so it is never
// statically prerendered at build time.
export const dynamic = "force-dynamic";

// What each metric can be asked, in the order a reader cares about it. The catalog computes
// this from the same rules the query engine enforces, so a chip here is a promise the API keeps.
function capabilities(metric: CatalogMetric): string[] {
  const count = metric.groupable_dimensions.length;
  return [
    `${count} ${count === 1 ? "dimension" : "dimensions"}`,
    ...(metric.supports.compare ? ["compare"] : []),
    ...(metric.supports.accumulate ? ["running total"] : []),
  ];
}

// One request, not two: `grain` + `compare` returns the series, the value, its previous window
// and the delta over a single resolved window. Fetching a metric and its delta separately could
// not guarantee both covered the same days.
async function leadsTrend() {
  return apiServer.POST("/api/v1/query", {
    body: {
      intent: {
        metric: "new_leads",
        grain: "month",
        date_range: "last_90_days",
        compare: {},
      },
      chart: { type: "line" },
    },
  });
}

export default async function DashboardPage() {
  const [catalog, trend] = await Promise.all([
    apiServer.GET("/api/v1/catalog"),
    leadsTrend(),
  ]);
  // `chart` is present exactly when the request asked for one, but the contract types it as
  // nullable for the callers that do not. Narrow it once here rather than assert it away.
  const trendChart = trend.data?.chart ?? null;

  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-col gap-1">
        <h1 className="text-[28px] font-semibold tracking-tight">
          Executive overview
        </h1>
        <p className="text-muted-foreground text-sm">
          {catalog.error
            ? "The metric catalog is unavailable."
            : `${catalog.data.metrics.length} metrics defined. The visuals are built on these next.`}
        </p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>New leads</CardTitle>
          <CardDescription>
            {/* The window the chart truly covers, resolved by the API — not the one we asked for. */}
            {trendChart?.subtitle ?? "Monthly, against the previous month."}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {trend.error ? (
            <ErrorState
              title="Can’t draw this chart"
              detail={trend.error.detail}
              allowed={trend.error.allowed}
            />
          ) : trendChart === null || trendChart.categories.length === 0 ? (
            <EmptyState
              title="No leads in this window"
              detail="Nothing was recorded in the last 90 days. That is an answer, not a failure."
            />
          ) : (
            <Chart spec={trendChart} />
          )}
        </CardContent>
      </Card>

      {catalog.error ? (
        <ErrorState
          title="Can’t reach the API"
          detail="Start it with make dev-api, then reload this page."
        />
      ) : catalog.data.metrics.length === 0 ? (
        <EmptyState
          title="No metrics defined"
          detail="Add one to the semantic registry, then run make validate."
        />
      ) : (
        <ul className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {catalog.data.metrics.map((metric) => (
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
