import { Chart } from "@/components/chart";
import { scalar } from "@/components/dashboard/headline";
import type { components } from "@/lib/api/schema";
import { formatValue } from "@/lib/format";

type QueryResponse = components["schemas"]["QueryResponse"];
type ChartSpec = components["schemas"]["ChartSpec"];

interface Fact {
  label: string;
  data?: QueryResponse;
}

interface HeroProps {
  /** Revenue scalar — the headline figure. */
  total?: QueryResponse;
  /** Revenue monthly, with a chart — the area/line beside the number. */
  trend?: { data?: QueryResponse };
  facts: Fact[];
  caption: string;
}

/** A currency headline reads better compact: $224.2M, not $224,190,000. */
function compactCurrency(value: number | null): string {
  if (value === null) return "—";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(value);
}

export function Hero({ total, trend, facts, caption }: HeroProps) {
  const revenue = total ? scalar(total.result) : null;
  const chart = trend?.data?.chart ?? null;

  return (
    <div className="bg-card ring-foreground/10 grid grid-cols-1 gap-8 rounded-2xl px-8 py-7 ring-1 lg:grid-cols-[1fr_1.05fr] lg:items-center lg:gap-10">
      <div>
        <div className="bg-primary mb-4 h-[3px] w-9 rounded-full" />
        <p className="text-muted-foreground text-[10.5px] font-bold tracking-[0.11em] uppercase">
          Total revenue · signed vouchers
        </p>
        <p
          className="font-display mt-2 text-[clamp(46px,6.2vw,66px)] leading-none font-bold tracking-[-0.045em]"
          data-numeric
        >
          {revenue ? compactCurrency(revenue.value) : "—"}
        </p>
        <p className="text-muted-foreground mt-4 text-[13px]">{caption}</p>

        <div className="border-border/60 mt-6 flex border-t pt-4">
          {facts.map((fact, i) => {
            const s = fact.data ? scalar(fact.data.result) : null;
            return (
              <div
                key={fact.label}
                className={
                  i < facts.length - 1 ? "border-border/60 mr-6 border-r pr-6" : ""
                }
              >
                <p className="text-muted-foreground text-[11.5px]">{fact.label}</p>
                <p
                  className="font-display mt-0.5 text-[19px] font-semibold tracking-tight"
                  data-numeric
                >
                  {s ? formatValue(s.value, s.format) : "—"}
                </p>
              </div>
            );
          })}
        </div>
      </div>

      <div>
        <div className="text-muted-foreground mb-1.5 flex justify-between text-[11px]">
          <span>Monthly revenue</span>
          <span>{chart?.subtitle ?? "Last 12 months"}</span>
        </div>
        {chart ? (
          <Chart spec={chart as ChartSpec} className="h-[176px] w-full" />
        ) : (
          <div className="bg-muted/40 h-[176px] w-full rounded-lg" />
        )}
      </div>
    </div>
  );
}
