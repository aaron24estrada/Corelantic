import { categoryRows } from "@/components/dashboard/headline";
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
import { formatValue } from "@/lib/format";

type QueryResponse = components["schemas"]["QueryResponse"];
type ErrorResponse = components["schemas"]["ErrorResponse"];

interface BarListCardProps {
  title: string;
  description?: string;
  result: { data?: QueryResponse; error?: ErrorResponse };
  emptyDetail: string;
  /** Cap the number of bars; the rest are the long tail. */
  limit?: number;
}

/**
 * A ranked horizontal bar list — a calmer, more premium read of a nominal breakdown than vertical
 * ECharts bars. One tone (identity is the label, not colour); the longest bar sets the scale.
 */
export function BarListCard({
  title,
  description,
  result,
  emptyDetail,
  limit = 6,
}: BarListCardProps) {
  const rows = result.data ? categoryRows(result.data.result) : null;
  const sorted = rows
    ? [...rows.rows].sort((a, b) => b.value - a.value).slice(0, limit)
    : [];
  const max = sorted[0]?.value ?? 0;

  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        {description ? <CardDescription>{description}</CardDescription> : null}
      </CardHeader>
      <CardContent>
        {result.error ? (
          <ErrorState
            title="Can’t draw this"
            detail={result.error.detail}
            allowed={result.error.allowed}
          />
        ) : sorted.length === 0 ? (
          <EmptyState title="Nothing to show" detail={emptyDetail} />
        ) : (
          <div className="flex flex-col gap-3">
            {sorted.map((row) => (
              <div
                key={row.label}
                className="grid grid-cols-[104px_1fr_56px] items-center gap-3"
              >
                <span className="text-foreground/80 truncate text-[12.5px]">
                  {row.label}
                </span>
                <span className="bg-muted h-2 overflow-hidden rounded-full">
                  <span
                    className="bg-chart-1 block h-full rounded-full"
                    style={{ width: `${max > 0 ? (row.value / max) * 100 : 0}%` }}
                  />
                </span>
                <span
                  className="text-right text-[12.5px] font-semibold"
                  data-numeric
                >
                  {formatValue(row.value, rows?.format ?? "number")}
                </span>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
