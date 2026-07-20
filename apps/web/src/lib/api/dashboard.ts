import "server-only";

import { apiServer } from "@/lib/api/server";
import type { components } from "@/lib/api/schema";

type QueryRequest = components["schemas"]["QueryRequest"];

// Every visual is one intent, declared here rather than inline, so the page stays a layout and
// what the dashboard asks is reviewable in one place. The vocabulary is what GET /catalog offers.

const query = (body: QueryRequest) => apiServer.POST("/api/v1/query", { body });

/** A KPI: one `grain + compare` request gives the weekly series (sparkline), latest value + delta. */
const kpi = (metric: string) =>
  query({
    intent: { metric, grain: "week", date_range: "last_90_days", compare: {} },
    chart: { type: "line" },
  });

/** A monthly trend line — the shared shape for the exec trends. */
const monthlyTrend = (metric: string) =>
  query({
    intent: { metric, grain: "month", date_range: "last_365_days" },
    chart: { type: "line" },
  });

/** A bare scalar — one number, no grouping, no time bucket. For hero + fact figures. */
const scalar = (metric: string) => query({ intent: { metric } });

/** A categorical breakdown — rows for a bar list or funnel, no chart. */
const breakdown = (metric: string, dimension: string) =>
  query({ intent: { metric, group_by: [dimension] } });

/** All the dashboard's data, fetched concurrently so one slow visual does not block the rest. */
export function dashboardData() {
  return {
    // Hero — revenue headline + monthly trend + supporting facts.
    revenueTotal: scalar("revenue"),
    revenueTrend: monthlyTrend("revenue"),
    factLeads: scalar("new_leads"),
    factVoucherRate: scalar("voucher_rate"),
    factBankComplete: scalar("leads_reached_bank_complete"),

    // Stat band.
    leads: kpi("new_leads"),
    voucherRate: kpi("voucher_rate"),
    answerRate: kpi("answer_rate"),
    totalCalls: kpi("total_calls"),
    agentConversion: kpi("agent_conversion_rate"),

    // Centre — leads trend + intake funnel.
    leadsTrend: monthlyTrend("new_leads"),
    funnel: breakdown("funnel_reach", "stage_name"),

    // Breakdowns.
    byChannel: breakdown("new_leads", "channel"),
    byState: breakdown("new_leads", "state"),

    // Call center — net-new over telephony.
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
  };
}
