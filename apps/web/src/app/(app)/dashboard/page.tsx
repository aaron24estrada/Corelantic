import { KpiPlaceholder } from "@/components/dashboard/kpi-placeholder";
import { KpiTile } from "@/components/dashboard/kpi-tile";
import { VisualCard } from "@/components/dashboard/visual-card";
import { dashboardData } from "@/lib/api/dashboard";

// Fetched per request from the private API (server-to-server), so it is never statically
// prerendered at build time.
export const dynamic = "force-dynamic";

export default async function DashboardPage() {
  const d = dashboardData();
  // Every request is already in flight (dashboardData fired them); awaiting together resolves
  // them concurrently — one slow query does not hold up the page. Order matches the array.
  const [
    leads,
    voucherRate,
    revenue,
    trend,
    revenueTrend,
    voucherRateTrend,
    funnel,
    byChannel,
    byState,
    byStatus,
    totalCalls,
    answerRate,
    avgWait,
    agentConversion,
    callsInOut,
    callsByDisposition,
    answerRateByRegion,
    conversionsByRegion,
  ] = await Promise.all([
    d.leads,
    d.voucherRate,
    d.revenue,
    d.trend,
    d.revenueTrend,
    d.voucherRateTrend,
    d.funnel,
    d.byChannel,
    d.byState,
    d.byStatus,
    d.totalCalls,
    d.answerRate,
    d.avgWait,
    d.agentConversion,
    d.callsInOut,
    d.callsByDisposition,
    d.answerRateByRegion,
    d.conversionsByRegion,
  ]);

  return (
    <div className="flex flex-col gap-12">
      <section className="flex flex-col gap-8">
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
        <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-5">
          {leads.data ? <KpiTile label="New leads" data={leads.data} /> : null}
          {voucherRate.data ? (
            <KpiTile label="Voucher rate" data={voucherRate.data} />
          ) : null}
          <KpiPlaceholder
            label="Marketing spend"
            note="Arrives with #37, this week."
          />
          {revenue.data ? (
            <KpiTile label="Revenue" data={revenue.data} />
          ) : null}
          <KpiPlaceholder label="ROAS" note="Needs spend (#37)." />
        </div>

        <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
          <div className="lg:col-span-2">
            <VisualCard
              title="New leads"
              description="Monthly, against the previous month."
              result={trend}
              emptyDetail="No leads recorded in the last year."
            />
          </div>
          <VisualCard
            title="Revenue"
            description="Monthly, against the previous month."
            result={revenueTrend}
            emptyDetail="No revenue recorded in the last year."
          />
          <VisualCard
            title="Voucher rate"
            description="Monthly, against the previous month."
            result={voucherRateTrend}
            emptyDetail="No intake recorded in the last year."
          />
          <div className="lg:col-span-2">
            <VisualCard
              title="Intake funnel"
              description="Distinct leads reaching each stage."
              result={funnel}
              emptyDetail="No stage history to build the funnel from."
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
          <VisualCard
            title="Leads by status"
            description="Current status of intake."
            result={byStatus}
            emptyDetail="No leads to break down by status."
          />
        </div>
      </section>

      <section className="flex flex-col gap-8">
        <header className="flex flex-col gap-1">
          <h2 className="text-[22px] font-semibold tracking-tight">
            Call center
          </h2>
          <p className="text-muted-foreground text-sm">
            Zoom call activity and agent performance — not on the embedded
            dashboard, read straight from the source.
          </p>
        </header>

        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          {totalCalls.data ? (
            <KpiTile label="Total calls" data={totalCalls.data} />
          ) : null}
          {answerRate.data ? (
            <KpiTile label="Answer rate" data={answerRate.data} />
          ) : null}
          {avgWait.data ? (
            <KpiTile label="Avg wait (sec)" data={avgWait.data} />
          ) : null}
          {agentConversion.data ? (
            <KpiTile label="Agent conversion" data={agentConversion.data} />
          ) : null}
        </div>

        <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
          <div className="lg:col-span-2">
            <VisualCard
              title="Call volume"
              description="Weekly, inbound vs outbound."
              result={callsInOut}
              emptyDetail="No calls recorded in the last 90 days."
            />
          </div>
          <VisualCard
            title="Calls by disposition"
            description="How call legs ended."
            result={callsByDisposition}
            emptyDetail="No calls to break down by disposition."
          />
          <VisualCard
            title="Answer rate by region"
            description="Share of legs picked up, per site."
            result={answerRateByRegion}
            emptyDetail="No calls to break down by region."
          />
          <VisualCard
            title="Conversions by region"
            description="Leads converted, per agent region."
            result={conversionsByRegion}
            emptyDetail="No agent activity to break down by region."
          />
        </div>
      </section>
    </div>
  );
}
