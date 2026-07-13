import type { EChartsCoreOption } from "echarts/core";

import type { components } from "@/lib/api/schema";
import { formatTick, formatValue } from "@/lib/format";
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
): EChartsCoreOption {
  const axisFormat = spec.y.format ?? "number";
  // A legend for two or more series, none for one — the title already names a lone series, and a
  // legend of one is furniture that steals plot height.
  const showLegend = spec.series.length > 1;

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
      valueFormatter: (value: unknown) =>
        formatValue(typeof value === "number" ? value : null, axisFormat),
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
    series: spec.series.map((series) => seriesOption(series, spec.type, theme)),
  };
}

function seriesOption(
  series: ChartSeries,
  type: ChartSpec["type"],
  theme: ChartTheme,
) {
  const color = theme.series[series.palette_index];
  const comparison = series.role === "comparison";

  const common = {
    name: series.name,
    // `null` is a gap, never a zero: a week with no rows, or the first bucket of a comparison,
    // which has nothing before it. ECharts breaks the line on null and would plot a 0.
    data: series.data,
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
    emphasis: { focus: "series" as const },
  };
}
