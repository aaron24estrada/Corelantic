import type { EChartsCoreOption } from "echarts/core";

import type { components } from "@/lib/api/schema";
import { formatTick, formatValue, toNumber } from "@/lib/format";
import type { ChartTheme } from "@/lib/chart/theme";

type ChartSpec = components["schemas"]["ChartSpec"];
type ChartSeries = components["schemas"]["ChartSeries"];

/**
 * The only place ECharts is named, and the only place the theme is applied.
 *
 * `ChartSpec` is the seam (decisions.md D-6): the API decides what to draw, and this adapts it
 * to one library. Swapping ECharts rewrites this file and nothing else — no component reaches
 * past it for a colour or a font, which is what keeps every chart looking like one product.
 *
 * Pure, so it is tested without a canvas.
 */
export function toEChartsOption(
  spec: ChartSpec,
  theme: ChartTheme,
  animate: boolean,
  compact = false,
): EChartsCoreOption {
  // A sparkline is the same spec drawn as a mark, not a chart: no axes, no grid, no legend, no
  // hover — just the line, so a KPI tile can carry its own recent history. Still one <Chart> and
  // one theme; the difference is chrome, not a second renderer.
  if (compact) return _sparkline(spec, theme, animate);

  const axisFormat = spec.y.format ?? "number";
  // A legend for two or more series, none for one — the title already names a lone series, and a
  // legend of one is furniture that steals plot height.
  const showLegend = spec.series.length > 1;
  // Only a lone line is filled: overlapping fills muddy each other and would imply a stack.
  const fill = spec.type === "line" && spec.series.length === 1;

  return {
    animation: animate,
    backgroundColor: "transparent",
    textStyle: { color: theme.text, fontFamily: "inherit" },
    grid: {
      left: 8,
      right: 16,
      top: showLegend ? 40 : 16,
      bottom: 8,
      // ECharts 6 deprecated `containLabel`, and without the LegacyGridContainLabel module it is
      // inert — axis labels get clipped rather than reserved for. This is its replacement.
      outerBoundsMode: "same",
      outerBoundsContain: "axisLabel",
    },
    legend: showLegend
      ? {
          top: 0,
          left: 0,
          icon: "roundRect",
          itemWidth: 10,
          itemHeight: 10,
          itemGap: 16,
          // Legend text wears the text token, never the series colour: a coloured swatch beside
          // it already carries identity, and coloured text fails contrast the swatch does not.
          textStyle: { color: theme.axis, fontSize: 12 },
        }
      : undefined,
    tooltip: {
      trigger: spec.type === "line" ? "axis" : "item",
      axisPointer: { type: "line", lineStyle: { color: theme.grid } },
      backgroundColor: theme.surface,
      borderColor: theme.grid,
      textStyle: { color: theme.text, fontSize: 12 },
      valueFormatter: (value: unknown) => formatValue(toNumber(value), axisFormat),
    },
    xAxis: {
      type: "category",
      data: spec.categories,
      boundaryGap: spec.type === "bar",
      axisLine: { lineStyle: { color: theme.grid } },
      axisTick: { show: false },
      axisLabel: { color: theme.axis, fontSize: 11, hideOverlap: true },
    },
    yAxis: {
      type: "value",
      // Recessive chrome: a hairline grid, no axis line. The data is the ink.
      splitLine: { lineStyle: { color: theme.grid, type: "solid" } },
      axisLine: { show: false },
      axisLabel: {
        color: theme.axis,
        fontSize: 11,
        formatter: (value: number) => formatTick(value, axisFormat),
      },
    },
    series: spec.series.map((series) => seriesOption(series, spec.type, theme, fill)),
  };
}

/** A hex from the theme as an rgba string, so an area gradient fades the line's own colour out. */
function withAlpha(hex: string, alpha: number): string {
  const h = hex.replace("#", "");
  const r = Number.parseInt(h.slice(0, 2), 16);
  const g = Number.parseInt(h.slice(2, 4), 16);
  const b = Number.parseInt(h.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

function _sparkline(
  spec: ChartSpec,
  theme: ChartTheme,
  animate: boolean,
): EChartsCoreOption {
  // Only the primary series is drawn — a tile shows its own trend, not its comparison; the delta
  // beside it already carries the change. Full-bleed grid so the line uses every pixel.
  const primary =
    spec.series.find((series) => series.role === "primary") ?? spec.series[0];
  return {
    animation: animate,
    backgroundColor: "transparent",
    grid: { left: 0, right: 0, top: 2, bottom: 2 },
    xAxis: {
      type: "category",
      data: spec.categories,
      show: false,
      boundaryGap: false,
    },
    yAxis: { type: "value", show: false, scale: true },
    series: primary
      ? [
          {
            type: "line",
            data: primary.data.map((value) => toNumber(value)),
            showSymbol: false,
            connectNulls: false,
            lineStyle: {
              color: theme.series[primary.palette_index],
              width: 1.5,
            },
          },
        ]
      : [],
  };
}

function seriesOption(
  series: ChartSeries,
  type: ChartSpec["type"],
  theme: ChartTheme,
  fill = false,
) {
  const color = theme.series[series.palette_index];
  const comparison = series.role === "comparison";

  const common = {
    name: series.name,
    // `null` is a gap, never a zero: a week with no rows, or a comparison's first bucket, which
    // has nothing before it. `toNumber` coerces the API's string decimals and preserves nulls.
    data: series.data.map((value) => toNumber(value)),
    color,
    // The comparison is the same entity in an earlier window, so it is told apart by weight and
    // stroke rather than by hue. A second colour would imply a second thing.
    itemStyle: { color, opacity: comparison ? 0.55 : 1 },
  };

  if (type === "bar") {
    return {
      ...common,
      type: "bar" as const,
      // A 2px surface gap between adjacent bars, so touching fills stay two marks.
      barCategoryGap: "35%",
      itemStyle: { ...common.itemStyle, borderRadius: [4, 4, 0, 0] },
    };
  }

  return {
    ...common,
    type: "line" as const,
    smooth: false,
    symbol: "circle",
    symbolSize: 8,
    showSymbol: false,
    connectNulls: false,
    lineStyle: {
      color,
      width: 2,
      opacity: comparison ? 0.55 : 1,
      type: comparison ? ("dashed" as const) : ("solid" as const),
    },
    // The line's own colour fading to nothing: emphasis, not a second encoding.
    ...(fill && !comparison
      ? {
          areaStyle: {
            color: {
              type: "linear" as const,
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: withAlpha(color, 0.2) },
                { offset: 1, color: withAlpha(color, 0) },
              ],
            },
          },
        }
      : {}),
    emphasis: { focus: "series" as const },
  };
}
