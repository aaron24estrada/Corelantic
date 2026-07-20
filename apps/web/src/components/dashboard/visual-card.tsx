import { Chart } from "@/components/chart";
import { DataCard } from "@/components/dashboard/data-card";
import type { components } from "@/lib/api/schema";

type QueryResponse = components["schemas"]["QueryResponse"];
type ErrorResponse = components["schemas"]["ErrorResponse"];

interface VisualCardProps {
  title: string;
  description?: string;
  /** The `{ data, error }` a single `apiServer.POST("/api/v1/query")` returns. */
  result: { data?: QueryResponse; error?: ErrorResponse };
  emptyDetail: string;
}

/** One intent → one `<Chart>`. The chart's own subtitle names the window it actually covers. */
export function VisualCard({
  title,
  description,
  result,
  emptyDetail,
}: VisualCardProps) {
  const chart = result.data?.chart ?? null;

  return (
    <DataCard
      title={title}
      description={chart?.subtitle ?? description}
      error={result.error}
      isEmpty={chart === null || chart.categories.length === 0}
      emptyDetail={emptyDetail}
    >
      {chart ? <Chart spec={chart} /> : null}
    </DataCard>
  );
}
