import type { components } from "@/lib/api/schema";

type ResultSet = components["schemas"]["ResultSet"];
type MetricFormat = components["schemas"]["MetricFormat"];

export interface Headline {
  value: number | null;
  format: MetricFormat;
  delta: number | null;
  deltaFormat: MetricFormat;
}

/**
 * Read the headline number, its change, and each one's format from a single `grain + compare`
 * result — never re-derived from the intent. `columns` names every role, so a tile, a band and a
 * chart all read one description and cannot disagree. The last bucket is the most recent value.
 */
export function headline(result: ResultSet): Headline {
  const columns = result.columns;
  const metric = columns.find((c) => c.role === "metric");
  const delta = columns.find((c) => c.role === "delta");
  const last = result.rows.at(-1) ?? {};
  const cell = (name: string | undefined): number | null => {
    const raw = name ? last[name] : null;
    return typeof raw === "number" ? raw : null;
  };
  return {
    value: cell(metric?.name),
    format: metric?.format ?? "number",
    delta: cell(delta?.name),
    deltaFormat: delta?.format ?? "number",
  };
}

export interface CategoryRow {
  label: string;
  value: number;
}

/**
 * A categorical breakdown as (label, value) rows for a CSS bar list or funnel: the dimension
 * column names each bar, the metric column is its length, and the metric's format renders the
 * value. A null dimension member is the source's unattributed bucket, shown as "(Blank)".
 */
export function categoryRows(result: ResultSet): {
  rows: CategoryRow[];
  format: MetricFormat;
} {
  const dim = result.columns.find((c) => c.role === "dimension");
  const metric = result.columns.find((c) => c.role === "metric");
  const rows: CategoryRow[] = [];
  for (const row of result.rows) {
    const rawLabel = dim ? row[dim.name] : null;
    const rawValue = metric ? row[metric.name] : null;
    if (typeof rawValue === "number") {
      rows.push({
        label: rawLabel == null ? "(Blank)" : String(rawLabel),
        value: rawValue,
      });
    }
  }
  return { rows, format: metric?.format ?? "number" };
}

/** The scalar value + its format from a no-grain result (one row, one metric column). */
export function scalar(result: ResultSet): { value: number | null; format: MetricFormat } {
  const metric = result.columns.find((c) => c.role === "metric");
  const first = result.rows[0] ?? {};
  const raw = metric ? first[metric.name] : null;
  return {
    value: typeof raw === "number" ? raw : null,
    format: metric?.format ?? "number",
  };
}
