import { DataCard } from "@/components/dashboard/data-card";
import { categoryRows } from "@/components/dashboard/headline";
import type { components } from "@/lib/api/schema";
import { formatValue } from "@/lib/format";

type QueryResponse = components["schemas"]["QueryResponse"];
type ErrorResponse = components["schemas"]["ErrorResponse"];

interface BarListCardProps {
  title: string;
  description?: string;
  result: { data?: QueryResponse; error?: ErrorResponse };
  emptyDetail: string;
  limit?: number;
}

/**
 * A ranked breakdown as horizontal bars. One tone throughout: the label carries identity, so
 * colouring each bar would re-encode what its length already says.
 */
export function BarListCard({
  title,
  description,
  result,
  emptyDetail,
  limit = 6,
}: BarListCardProps) {
  const breakdown = result.data ? categoryRows(result.data.result) : null;
  const bars =
    breakdown?.rows
      .toSorted((a, b) => b.value - a.value)
      .slice(0, limit) ?? [];
  const longest = bars[0]?.value ?? 0;

  return (
    <DataCard
      title={title}
      description={description}
      error={result.error}
      isEmpty={bars.length === 0}
      emptyDetail={emptyDetail}
    >
      <div className="flex flex-col gap-3">
        {bars.map((bar) => (
          <div
            key={bar.label}
            className="grid grid-cols-[104px_1fr_56px] items-center gap-3"
          >
            <span className="text-foreground/80 truncate text-[12.5px]">
              {bar.label}
            </span>
            <span className="bg-muted h-2 overflow-hidden rounded-full">
              <span
                className="bg-chart-1 block h-full rounded-full"
                style={{ width: `${longest > 0 ? (bar.value / longest) * 100 : 0}%` }}
              />
            </span>
            <span className="text-right text-[12.5px] font-semibold" data-numeric>
              {formatValue(bar.value, breakdown?.format ?? "number")}
            </span>
          </div>
        ))}
      </div>
    </DataCard>
  );
}
