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

/** All the dashboard's data, fetched concurrently so one slow visual does not block the rest. */
export function dashboardData() {
  return {
    leads: kpi("new_leads"),
    voucherRate: kpi("voucher_rate"),
    revenue: kpi("revenue"),
    trend: query({
      intent: {
        metric: "new_leads",
        grain: "month",
        date_range: "last_365_days",
        compare: {},
      },
      chart: { type: "line" },
    }),
    byChannel: query({
      intent: { metric: "new_leads", group_by: ["channel"] },
      chart: { type: "bar" },
    }),
    byState: query({
      intent: { metric: "new_leads", group_by: ["state"] },
      chart: { type: "bar" },
    }),
  };
}
