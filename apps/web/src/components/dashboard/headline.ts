/**
 * Reading values out of a `ResultSet`.
 *
 * Every format comes from the column that describes the value, never re-derived from the metric
 * name — that is what keeps a tile, a chart and a table saying the same thing.
 */
import type { components } from "@/lib/api/schema";
import { toNumber } from "@/lib/format";

type ResultSet = components["schemas"]["ResultSet"];
type MetricFormat = components["schemas"]["MetricFormat"];

export interface Headline {
  value: number | null;
  format: MetricFormat;
  delta: number | null;
  deltaFormat: MetricFormat;
}

export interface CategoryRow {
  label: string;
  value: number;
}

/** The latest bucket of a `grain + compare` result: its value, its change, and both formats. */
export function headline(result: ResultSet): Headline {
  const metric = result.columns.find((column) => column.role === "metric");
  const delta = result.columns.find((column) => column.role === "delta");
  const latest = result.rows.at(-1) ?? {};
  const cell = (name: string | undefined) => toNumber(name ? latest[name] : null);

  return {
    value: cell(metric?.name),
    format: metric?.format ?? "number",
    delta: cell(delta?.name),
    deltaFormat: delta?.format ?? "number",
  };
}

/** The single value of an ungrouped, ungrained result. */
export function scalar(result: ResultSet): {
  value: number | null;
  format: MetricFormat;
} {
  const metric = result.columns.find((column) => column.role === "metric");
  const [first] = result.rows;

  return {
    value: toNumber(metric && first ? first[metric.name] : null),
    format: metric?.format ?? "number",
  };
}

/** A breakdown as (label, value) rows. A null member is the source's own unattributed bucket. */
export function categoryRows(result: ResultSet): {
  rows: CategoryRow[];
  format: MetricFormat;
} {
  const dimension = result.columns.find((column) => column.role === "dimension");
  const metric = result.columns.find((column) => column.role === "metric");
  const rows: CategoryRow[] = [];

  for (const row of result.rows) {
    const value = toNumber(metric ? row[metric.name] : null);
    if (value === null) continue;
    const label = dimension ? row[dimension.name] : null;
    rows.push({ label: label == null ? "(Blank)" : String(label), value });
  }

  return { rows, format: metric?.format ?? "number" };
}
