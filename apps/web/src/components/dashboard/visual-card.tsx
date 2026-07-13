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

type QueryResponse = components["schemas"]["QueryResponse"];
type ErrorResponse = components["schemas"]["ErrorResponse"];

interface VisualCardProps {
  title: string;
  description?: string;
  /** The `{ data, error }` a single `apiServer.POST("/api/v1/query")` returns. */
  result: { data?: QueryResponse; error?: ErrorResponse };
  emptyDetail: string;
}

/**
 * One card = one intent → one `<Chart>`. Every data surface handles loading, empty and error
 * explicitly (standards/nextjs.md); this is the one place that wiring lives so no visual forgets
 * it. `ErrorState` renders the 422's `allowed` list, so a refusal names the options.
 */
export function VisualCard({
  title,
  description,
  result,
  emptyDetail,
}: VisualCardProps) {
  const chart = result.data?.chart ?? null;
  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <CardDescription>
          {chart?.subtitle ?? description ?? " "}
        </CardDescription>
      </CardHeader>
      <CardContent>
        {result.error ? (
          <ErrorState
            title="Can’t draw this"
            detail={result.error.detail}
            allowed={result.error.allowed}
          />
        ) : chart === null || chart.categories.length === 0 ? (
          <EmptyState title="Nothing to show" detail={emptyDetail} />
        ) : (
          <Chart spec={chart} />
        )}
      </CardContent>
    </Card>
  );
}
