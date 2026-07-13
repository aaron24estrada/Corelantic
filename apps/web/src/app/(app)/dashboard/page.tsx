import { KpiPlaceholder } from "@/components/dashboard/kpi-placeholder";
import { KpiTile } from "@/components/dashboard/kpi-tile";
import { VisualCard } from "@/components/dashboard/visual-card";
import { dashboardData } from "@/lib/api/dashboard";

// Fetched per request from the private API (server-to-server), so it is never statically
// prerendered at build time.
export const dynamic = "force-dynamic";

export default async function DashboardPage() {
  const data = dashboardData();
  // Resolve every visual's request concurrently; one slow query does not hold up the page.
  const [leads, voucherRate, revenue, trend, byChannel, byState] =
    await Promise.all([
      data.leads,
      data.voucherRate,
      data.revenue,
      data.trend,
      data.byChannel,
      data.byState,
    ]);

  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-col gap-1">
        <h1 className="text-[28px] font-semibold tracking-tight">
          Executive overview
        </h1>
        <p className="text-muted-foreground text-sm">
          Leads, intake and revenue over KRW&rsquo;s live source.
        </p>
      </header>

      {/* The KRW Revenue Intelligence KPI row. Three tiles are live; Spend and ROAS wait on
          #37's marketing_budget, shown as placeholders so the row keeps its shape. */}
      <section className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-5">
        {leads.data ? <KpiTile label="New leads" data={leads.data} /> : null}
        {voucherRate.data ? (
          <KpiTile label="Voucher rate" data={voucherRate.data} />
        ) : null}
        <KpiPlaceholder
          label="Marketing spend"
          note="Arrives with #37, this week."
        />
        {revenue.data ? <KpiTile label="Revenue" data={revenue.data} /> : null}
        <KpiPlaceholder label="ROAS" note="Needs spend (#37)." />
      </section>

      <section className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <div className="lg:col-span-2">
          <VisualCard
            title="New leads"
            description="Monthly, against the previous month."
            result={trend}
            emptyDetail="No leads recorded in the last year."
          />
        </div>
        <VisualCard
          title="Leads by channel"
          description="Where intake comes from."
          result={byChannel}
          emptyDetail="No leads to break down by channel."
        />
        <VisualCard
          title="Leads by state"
          description="Geographic spread of intake."
          result={byState}
          emptyDetail="No leads to break down by state."
        />
      </section>
    </div>
  );
}
