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

/**
 * One surface, hairline-divided columns — a stat band, not a row of boxed cards. Each column is a
 * KPI: headline value in the display face, its WoW change and a chrome-less sparkline. The change
 * stays neutral ink because a rise is not always good (spam, wait time) — the dashboard states
 * direction without editorialising which way is better.
 */
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
  const cell = data ? headline(data.result) : null;
  const delta = cell?.delta ?? null;
  const direction = delta === null ? "" : delta > 0 ? "▲" : delta < 0 ? "▼" : "→";

  return (
    <div className="border-border/50 flex flex-col gap-2 border-r border-b p-4">
      <p className="text-muted-foreground text-[11px] font-semibold tracking-wide uppercase">
        {label}
      </p>
      <p
        className="font-display text-[23px] leading-none font-semibold tracking-tight"
        data-numeric
      >
        {cell ? formatValue(cell.value, cell.format) : "—"}
      </p>
      <div className="mt-auto flex items-center justify-between gap-2 pt-1">
        <span
          className={cn(
            "text-muted-foreground text-[11px]",
            delta === null && "invisible",
          )}
          data-numeric
        >
          {direction} {formatDelta(delta, cell?.deltaFormat ?? "number")}
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
