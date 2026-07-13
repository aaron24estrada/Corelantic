import { Chart } from "@/components/chart";
import { Card, CardContent } from "@/components/ui/card";
import type { components } from "@/lib/api/schema";
import { formatDelta, formatValue } from "@/lib/format";
import { cn } from "@/lib/utils";

type QueryResponse = components["schemas"]["QueryResponse"];
type ResultSet = components["schemas"]["ResultSet"];
type ChartSpec = components["schemas"]["ChartSpec"];
type MetricFormat = components["schemas"]["MetricFormat"];

interface KpiTileProps {
  label: string;
  /** One `grain + compare` query: the series is the sparkline, its last row the headline. */
  data: QueryResponse;
}

// Read the headline number, its change, and the format from the one query's result — never
// re-derive them. `describe_columns` names each role, so the tile and the chart agree.
function headline(result: ResultSet): {
  value: number | null;
  format: MetricFormat;
  delta: number | null;
  deltaFormat: MetricFormat;
} {
  const columns = result.columns;
  const metric = columns.find((c) => c.role === "metric");
  const delta = columns.find((c) => c.role === "delta");
  // The last bucket is the most recent — the value a KPI headline reports.
  const last = result.rows.at(-1) ?? {};
  const cell = (name: string | undefined): number | null => {
    const raw = name ? last[name] : null;
    return typeof raw === "number" ? raw : null;
  };
  return {
    value: cell(metric?.name),
    format: metric?.format ?? "number",
    delta: cell(delta?.name),
    deltaFormat: delta?.format ?? "number",
  };
}

export function KpiTile({ label, data }: KpiTileProps) {
  const { value, format, delta, deltaFormat } = headline(data.result);
  // A rise is not always good (spam calls, wait time), so the arrow states direction and the
  // colour stays neutral — the dashboard does not editorialise which way is better.
  const direction =
    delta === null ? "" : delta > 0 ? "▲" : delta < 0 ? "▼" : "→";

  return (
    <Card>
      <CardContent className="flex flex-col gap-1 pt-1">
        <p className="text-muted-foreground text-sm font-medium">{label}</p>
        <p className="text-2xl font-semibold tracking-tight" data-numeric>
          {formatValue(value, format)}
        </p>
        <div className="flex items-center justify-between gap-2">
          <span
            className={cn(
              "text-muted-foreground text-xs",
              delta === null && "invisible",
            )}
            data-numeric
          >
            {/* A rise is not always good (spam, wait time), so the copy states the change and its
                direction without colouring it — the dashboard does not say which way is better. */}
            {direction} {formatDelta(delta, deltaFormat)} vs. prev.
          </span>
          {data.chart ? (
            <Chart
              spec={data.chart as ChartSpec}
              compact
              className="h-8 w-24 shrink-0"
            />
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
}
