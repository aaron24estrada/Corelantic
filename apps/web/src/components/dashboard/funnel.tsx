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

// Stage reach is monotonic, so sorting by value descending reproduces the funnel order without
// the registry declaring one (the ordered-members gap is tracked in #14). These trims keep the
// long source names readable; an unmatched name falls through unchanged.
const SHORT: Record<string, string> = {
  Lead: "Lead",
  "Voucher (Initial Intake)": "Voucher",
  "X-Ray Received": "X-Ray",
  "X-Ray to B-Read": "X-Ray → B-Read",
  "B-Read Results": "B-Read",
  "Sched. for Clinic": "Clinic",
  "Bank Incomplete": "Bank (incomplete)",
  "Bank Complete": "Bank complete",
};

interface FunnelCardProps {
  title: string;
  description?: string;
  result: { data?: QueryResponse; error?: ErrorResponse };
  emptyDetail: string;
}

const pct = (n: number) => `${(n * 100).toFixed(n < 0.1 ? 1 : 0)}%`;

export function FunnelCard({
  title,
  description,
  result,
  emptyDetail,
}: FunnelCardProps) {
  const parsed = result.data ? categoryRows(result.data.result) : null;
  const stages = parsed
    ? [...parsed.rows].sort((a, b) => b.value - a.value)
    : [];
  const base = stages[0]?.value ?? 0;

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
        ) : stages.length === 0 ? (
          <EmptyState title="Nothing to show" detail={emptyDetail} />
        ) : (
          <div className="flex flex-col">
            {stages.map((stage, i) => {
              const prev = stages[i - 1];
              return (
                <div key={stage.label}>
                  {prev ? (
                    <div className="text-muted-foreground grid grid-cols-[118px_1fr_auto] gap-4 py-1 text-[10.5px]">
                      <span />
                      <span className="border-border/70 border-l pl-2">
                        {pct(stage.value / prev.value)} reach {SHORT[stage.label] ?? stage.label}
                      </span>
                    </div>
                  ) : null}
                  <div className="grid grid-cols-[118px_1fr_auto] items-center gap-4">
                    <span className="text-[12.5px]">
                      {SHORT[stage.label] ?? stage.label}
                    </span>
                    <span className="bg-muted block h-8 overflow-hidden rounded-lg">
                      <span
                        className="bg-chart-1 block h-full rounded-lg"
                        style={{
                          width: `${base > 0 ? (stage.value / base) * 100 : 0}%`,
                        }}
                      />
                    </span>
                    <span className="min-w-[80px] text-right">
                      <span
                        className="block text-[13.5px] font-semibold"
                        data-numeric
                      >
                        {formatValue(stage.value, parsed?.format ?? "number")}
                      </span>
                      <span
                        className="text-muted-foreground block text-[11px]"
                        data-numeric
                      >
                        {base > 0 ? pct(stage.value / base) : "—"}
                      </span>
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
