import { DataCard } from "@/components/dashboard/data-card";
import { categoryRows } from "@/components/dashboard/headline";
import type { components } from "@/lib/api/schema";
import { formatValue } from "@/lib/format";

type QueryResponse = components["schemas"]["QueryResponse"];
type ErrorResponse = components["schemas"]["ErrorResponse"];

// The source's stage names are long; these read better on a bar. Unlisted names pass through.
const STAGE_LABELS: Record<string, string> = {
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

/** A share of a whole, or "—" when there is no whole to be a share of. */
const share = (part: number, whole: number) => {
  if (whole <= 0) return "—";
  const pct = (part / whole) * 100;
  return `${pct.toFixed(pct < 10 ? 1 : 0)}%`;
};

const widthPercent = (part: number, whole: number) =>
  whole > 0 ? (part / whole) * 100 : 0;

const labelFor = (stage: string) => STAGE_LABELS[stage] ?? stage;

/**
 * The intake funnel as bars, with the conversion between each step.
 *
 * Stage reach only decreases, so sorting by value descending reproduces the funnel order without
 * the registry declaring one — the ordered-members gap tracked in #14.
 */
export function FunnelCard({
  title,
  description,
  result,
  emptyDetail,
}: FunnelCardProps) {
  const breakdown = result.data ? categoryRows(result.data.result) : null;
  const stages = breakdown?.rows.toSorted((a, b) => b.value - a.value) ?? [];
  const entered = stages[0]?.value ?? 0;

  return (
    <DataCard
      title={title}
      description={description}
      error={result.error}
      isEmpty={stages.length === 0}
      emptyDetail={emptyDetail}
    >
      <div className="flex flex-col">
        {stages.map((stage, index) => {
          const previous = stages[index - 1];
          return (
            <div key={stage.label}>
              {previous ? (
                <p className="text-muted-foreground grid grid-cols-[118px_1fr_auto] gap-4 py-1 text-[10.5px]">
                  <span />
                  <span className="border-border/70 border-l pl-2">
                    {share(stage.value, previous.value)} reach {labelFor(stage.label)}
                  </span>
                </p>
              ) : null}

              <div className="grid grid-cols-[118px_1fr_auto] items-center gap-4">
                <span className="text-[12.5px]">{labelFor(stage.label)}</span>
                <span className="bg-muted block h-8 overflow-hidden rounded-lg">
                  <span
                    className="bg-chart-1 block h-full rounded-lg"
                    style={{ width: `${widthPercent(stage.value, entered)}%` }}
                  />
                </span>
                <span className="min-w-[80px] text-right">
                  <span className="block text-[13.5px] font-semibold" data-numeric>
                    {formatValue(stage.value, breakdown?.format ?? "number")}
                  </span>
                  <span
                    className="text-muted-foreground block text-[11px]"
                    data-numeric
                  >
                    {share(stage.value, entered)}
                  </span>
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </DataCard>
  );
}
