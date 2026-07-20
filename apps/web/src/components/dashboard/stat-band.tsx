import { Chart } from "@/components/chart";
import { headline } from "@/components/dashboard/headline";
import type { components } from "@/lib/api/schema";
import { formatDelta, formatValue } from "@/lib/format";
import { cn } from "@/lib/utils";

type QueryResponse = components["schemas"]["QueryResponse"];
type ChartSpec = components["schemas"]["ChartSpec"];

interface Stat {
  label: string;
  data?: QueryResponse;
}

/** One surface with hairline-divided columns, rather than a row of separately boxed tiles. */
export function StatBand({ stats }: { stats: Stat[] }) {
  return (
    <div className="bg-card ring-foreground/10 grid grid-cols-2 overflow-hidden rounded-xl ring-1 sm:grid-cols-3 lg:grid-cols-5">
      {stats.map((stat) => (
        <StatCell key={stat.label} {...stat} />
      ))}
    </div>
  );
}

function StatCell({ label, data }: Stat) {
  const stat = data ? headline(data.result) : null;
  const delta = stat?.delta ?? null;
  // Direction without judgement: a rise is not always good (spam calls, wait time), so the arrow
  // states which way it moved and the colour stays neutral.
  const arrow = delta === null ? "" : delta > 0 ? "▲" : delta < 0 ? "▼" : "→";

  return (
    <div className="border-border/50 flex flex-col gap-2 border-r border-b p-4">
      <p className="text-muted-foreground text-[11px] font-semibold tracking-wide uppercase">
        {label}
      </p>
      <p
        className="font-display text-[23px] leading-none font-semibold tracking-tight"
        data-numeric
      >
        {stat ? formatValue(stat.value, stat.format) : "—"}
      </p>
      <div className="mt-auto flex items-center justify-between gap-2 pt-1">
        <span
          className={cn(
            "text-muted-foreground text-[11px]",
            delta === null && "invisible",
          )}
          data-numeric
        >
          {arrow} {formatDelta(delta, stat?.deltaFormat ?? "number")}
        </span>
        {data?.chart ? (
          <Chart
            spec={data.chart as ChartSpec}
            compact
            className="h-6 w-20 shrink-0"
          />
        ) : null}
      </div>
    </div>
  );
}
