import type { components } from "@/lib/api/schema";

type MetricFormat = components["schemas"]["MetricFormat"];

/**
 * Format a value the way its column says to, never the way its name suggests.
 *
 * The API decides the format from the metric's definition and publishes it on every column, so
 * a chart, a tile and a table all read one description and cannot disagree. The case that bites:
 * the delta of a percent metric is `percent_point`, not `percent` — 20% rising to 24% gained four
 * *points*, and calling that "+4%" is true of the ratio and wrong about the business.
 */
export function formatValue(
  value: number | null,
  format: MetricFormat,
): string {
  if (value === null || Number.isNaN(value)) return "—";

  switch (format) {
    case "currency":
      return new Intl.NumberFormat("en-US", {
        style: "currency",
        currency: "USD",
        maximumFractionDigits: 0,
      }).format(value);
    case "percent":
      return new Intl.NumberFormat("en-US", {
        style: "percent",
        maximumFractionDigits: 1,
      }).format(value);
    case "percent_point":
      // Already in points: the API sends 0.04 for "four points", the same scale as the rate it
      // describes. Rendering it through `style: "percent"` would say "4%" and mean something else.
      return `${signed(value * 100, 1)} pts`;
    case "number":
      return new Intl.NumberFormat("en-US", {
        maximumFractionDigits: 0,
      }).format(value);
  }
}

/** A signed number, so a delta reads as a direction and not just a magnitude. */
export function signed(value: number, fractionDigits = 0): string {
  const formatted = new Intl.NumberFormat("en-US", {
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  }).format(Math.abs(value));
  if (value > 0) return `+${formatted}`;
  if (value < 0) return `−${formatted}`; // U+2212, which aligns with digits; the hyphen does not
  return formatted;
}

/**
 * A change, always signed so it reads as a direction.
 *
 * Distinct from `formatValue` because a delta must show its sign even when positive (`+12%`, not
 * `12%`), and because the API sends a percent delta as a ratio (`-0.44` → `-44%`) and a
 * percent-point delta already in points (`0.04` → `+4.0 pts`). The column's format says which.
 */
export function formatDelta(
  value: number | null,
  format: MetricFormat,
): string {
  if (value === null || Number.isNaN(value)) return "—";
  switch (format) {
    case "percent":
      return `${signed(value * 100, 1)}%`;
    case "percent_point":
      return `${signed(value * 100, 1)} pts`;
    case "currency":
      return `${value < 0 ? "−" : "+"}${formatValue(Math.abs(value), "currency")}`;
    case "number":
      return signed(value);
  }
}

/** Axis ticks are cramped, so they abbreviate where a tooltip would not. */
export function formatTick(value: number, format: MetricFormat): string {
  if (format === "percent") {
    return new Intl.NumberFormat("en-US", {
      style: "percent",
      maximumFractionDigits: 0,
    }).format(value);
  }
  if (format === "percent_point") return `${signed(value * 100, 0)}`;

  const abbreviated = new Intl.NumberFormat("en-US", {
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(value);
  return format === "currency" ? `$${abbreviated}` : abbreviated;
}
