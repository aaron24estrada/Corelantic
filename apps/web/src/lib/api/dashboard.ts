import "server-only";

import { apiServer } from "@/lib/api/server";
import type { components } from "@/lib/api/schema";

type QueryRequest = components["schemas"]["QueryRequest"];

// Every visual on the dashboard is one intent. They live here, not inline in the page, so the
// page stays a declarative layout and the "what is asked" is reviewable in one place — the
// vocabulary is exactly what GET /catalog advertises.

const query = (body: QueryRequest) => apiServer.POST("/api/v1/query", { body });

/**
 * A KPI tile: one `grain + compare` request returns the weekly series (the sparkline), the
 * latest value, its previous week and the delta — over one resolved window, so the headline and
 * its change always cover the same days. Never two requests; that could not guarantee that.
 */
const kpi = (metric: string) =>
  query({
    intent: { metric, grain: "week", date_range: "last_90_days", compare: {} },
    chart: { type: "line" },
  });

/** A monthly trend line against the previous month — the shared shape for the exec trends. */
const monthlyTrend = (metric: string) =>
  query({
    intent: { metric, grain: "month", date_range: "last_365_days", compare: {} },
    chart: { type: "line" },
  });

/** A single-series categorical bar: one metric broken down by one nominal dimension. */
const breakdown = (metric: string, dimension: string) =>
  query({
    intent: { metric, group_by: [dimension] },
    chart: { type: "bar" },
  });

/** All the dashboard's data, fetched concurrently so one slow visual does not block the rest. */
export function dashboardData() {
  return {
    // Executive — leads, revenue, intake funnel.
    leads: kpi("new_leads"),
    voucherRate: kpi("voucher_rate"),
    revenue: kpi("revenue"),
    trend: monthlyTrend("new_leads"),
    revenueTrend: monthlyTrend("revenue"),
    voucherRateTrend: monthlyTrend("voucher_rate"),
    funnel: breakdown("funnel_reach", "stage_name"),
    byChannel: breakdown("new_leads", "channel"),
    byState: breakdown("new_leads", "state"),
    byStatus: breakdown("new_leads", "status"),

    // Call center — net-new over telephony (zoom_calls, agent_stats); not on KRW's dashboard.
    totalCalls: kpi("total_calls"),
    answerRate: kpi("answer_rate"),
    avgWait: kpi("avg_wait_time_sec"),
    agentConversion: kpi("agent_conversion_rate"),
    // Inbound vs outbound over time: a pivoted trend, so grain + group_by, no compare.
    callsInOut: query({
      intent: {
        metric: "total_calls",
        grain: "week",
        group_by: ["call_direction"],
        date_range: "last_90_days",
      },
      chart: { type: "line" },
    }),
    callsByDisposition: breakdown("total_calls", "call_result"),
    answerRateByRegion: breakdown("answer_rate", "call_region"),
    conversionsByRegion: breakdown("leads_converted", "agent_region"),
  };
}
