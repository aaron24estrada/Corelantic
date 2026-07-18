import { BarListCard } from "@/components/dashboard/bar-list";
import { FunnelCard } from "@/components/dashboard/funnel";
import { Hero } from "@/components/dashboard/hero";
import { StatBand } from "@/components/dashboard/stat-band";
import { VisualCard } from "@/components/dashboard/visual-card";
import { dashboardData } from "@/lib/api/dashboard";

// Fetched per request from the private API (server-to-server), so it is never statically
// prerendered at build time.
export const dynamic = "force-dynamic";

export default async function DashboardPage() {
  const d = dashboardData();
  // Every request is already in flight (dashboardData fired them); awaiting together resolves
  // them concurrently — one slow query does not hold up the page.
  const [
    revenueTotal,
    revenueTrend,
    factLeads,
    factVoucherRate,
    factBankComplete,
    leads,
    voucherRate,
    answerRate,
    totalCalls,
    agentConversion,
    leadsTrend,
    funnel,
    byChannel,
    byState,
    callsInOut,
    callsByDisposition,
  ] = await Promise.all([
    d.revenueTotal,
    d.revenueTrend,
    d.factLeads,
    d.factVoucherRate,
    d.factBankComplete,
    d.leads,
    d.voucherRate,
    d.answerRate,
    d.totalCalls,
    d.agentConversion,
    d.leadsTrend,
    d.funnel,
    d.byChannel,
    d.byState,
    d.callsInOut,
    d.callsByDisposition,
  ]);

  return (
    <div className="flex flex-col gap-7">
      <header className="flex items-baseline justify-between gap-4">
        <h1 className="text-[26px] font-semibold tracking-tight">
          Executive overview
        </h1>
        <p className="text-muted-foreground text-xs">
          Live · KRW Azure SQL · <span data-numeric>gold_tspot</span>
        </p>
      </header>

      <Hero
        total={revenueTotal.data}
        trend={revenueTrend}
        caption="Signed vouchers valued at the $6,000 average case fee."
        facts={[
          { label: "New leads", data: factLeads.data },
          { label: "Voucher rate", data: factVoucherRate.data },
          { label: "Bank complete", data: factBankComplete.data },
        ]}
      />

      <StatBand
        stats={[
          { label: "New leads", data: leads.data },
          { label: "Voucher rate", data: voucherRate.data },
          { label: "Answer rate", data: answerRate.data },
          { label: "Total calls", data: totalCalls.data },
          { label: "Agent conv.", data: agentConversion.data },
        ]}
      />

      <section className="grid grid-cols-1 gap-4 lg:grid-cols-[1.6fr_1fr]">
        <VisualCard
          title="New leads"
          description="Monthly, last 12 months."
          result={leadsTrend}
          emptyDetail="No leads recorded in the last year."
        />
        <FunnelCard
          title="Intake funnel"
          description="Distinct leads reaching each milestone."
          result={funnel}
          emptyDetail="No stage history to build the funnel from."
        />
      </section>

      <section className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <BarListCard
          title="Leads by channel"
          description="Where intake comes from."
          result={byChannel}
          emptyDetail="No leads to break down by channel."
        />
        <BarListCard
          title="Leads by state"
          description="Top geographies · some leads carry no geo."
          result={byState}
          emptyDetail="No leads to break down by state."
        />
      </section>

      <section className="flex flex-col gap-4">
        <div className="flex items-baseline gap-3">
          <h2 className="text-muted-foreground text-[13px] font-bold tracking-[0.09em] uppercase">
            Call center
          </h2>
          <span className="text-muted-foreground text-xs">
            Zoom activity &amp; agent performance — net-new, never on the embedded dashboard
          </span>
          <span className="bg-border/70 h-px flex-1" />
        </div>
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1.6fr_1fr]">
          <VisualCard
            title="Call volume"
            description="Weekly, inbound vs outbound · last 90 days."
            result={callsInOut}
            emptyDetail="No calls recorded in the last 90 days."
          />
          <BarListCard
            title="Calls by disposition"
            description="How call legs ended."
            result={callsByDisposition}
            emptyDetail="No calls to break down by disposition."
          />
        </div>
      </section>

      <p className="text-muted-foreground border-border/60 mt-2 border-t pt-4 text-[11.5px]">
        Corelantic · reading KRW’s live Azure SQL (<span data-numeric>gold_tspot</span>).
        Marketing spend &amp; ROAS arrive with cross-schema access (#37).
      </p>
    </div>
  );
}
