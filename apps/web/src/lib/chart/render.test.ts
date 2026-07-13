import { LineChart } from "echarts/charts";
import {
  GridComponent,
  LegendComponent,
  TooltipComponent,
} from "echarts/components";
import * as echarts from "echarts/core";
import { SVGRenderer } from "echarts/renderers";
import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";

import type { components } from "@/lib/api/schema";
import { toEChartsOption } from "@/lib/chart/echarts-option";
import type { ChartTheme } from "@/lib/chart/theme";

type ChartSpec = components["schemas"]["ChartSpec"];

/**
 * The adapter's output, actually drawn.
 *
 * Asserting on the option object proves we built the object we meant to; it does not prove
 * ECharts accepts it. ECharts renders to an SVG string in Node, so the real renderer runs here
 * with no browser and no canvas — a malformed axis or an option key that quietly does nothing
 * shows up as a missing mark rather than as a passing test.
 *
 * `<Chart>` registers the canvas renderer; this registers the SVG one. Same charts, same option.
 */
echarts.use([
  LineChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  SVGRenderer,
]);

const THEME: ChartTheme = {
  series: [
    "#0071e3",
    "#05a873",
    "#c38406",
    "#e34948",
    "#dc709a",
    "#eb6834",
    "#4a3aa7",
    "#008300",
  ],
  axis: "#6e6e73",
  grid: "#d8d8dc",
  surface: "#ffffff",
  text: "#1d1d1f",
};

function draw(spec: ChartSpec): string {
  const chart = echarts.init(null, null, {
    renderer: "svg",
    ssr: true,
    width: 640,
    height: 320,
  });
  chart.setOption(toEChartsOption(spec, THEME, false));
  const svg = chart.renderToSVGString();
  chart.dispose();
  return svg;
}

/**
 * Everything ECharts said while this file drew its charts.
 *
 * Captured from before the *first* draw, because ECharts logs each deprecation once per process:
 * a spy installed inside the last test would find the warning already spent, and would pass no
 * matter what the option contained. A probe that cannot fail proves nothing.
 */
const complaints: string[] = [];

beforeAll(() => {
  for (const level of ["log", "warn", "error"] as const) {
    vi.spyOn(console, level).mockImplementation((...args: unknown[]) => {
      complaints.push(args.join(" "));
    });
  }
});

afterAll(() => vi.restoreAllMocks());

const base: ChartSpec = {
  type: "line",
  title: "Total calls",
  subtitle: "12 Apr 2026 – 10 Jul 2026",
  categories: ["2026-06-01", "2026-06-08", "2026-06-15"],
  x: { label: "Period", format: null },
  y: { label: "Total calls", format: "number" },
  series: [],
};

describe("a chart spec, actually rendered", () => {
  it("paints each series in the hue its palette slot names", () => {
    const svg = draw({
      ...base,
      series: [
        {
          name: "inbound",
          data: [3, 4, 5],
          format: "number",
          role: "primary",
          palette_index: 0,
        },
        {
          name: "outbound",
          data: [7, 6, 5],
          format: "number",
          role: "primary",
          palette_index: 1,
        },
      ],
    });

    expect(svg).toContain(THEME.series[0]);
    expect(svg).toContain(THEME.series[1]);
    // Slot 3 was never asked for, so it must not appear. This is what catches a renderer that
    // falls back to ECharts' own default palette when it cannot read ours.
    expect(svg).not.toContain(THEME.series[2]);
  });

  it("draws the comparison dashed, in its primary's hue", () => {
    const svg = draw({
      ...base,
      series: [
        {
          name: "Total calls",
          data: [3, 4, 5],
          format: "number",
          role: "primary",
          palette_index: 0,
        },
        {
          name: "Previous total calls",
          data: [null, 3, 4],
          format: "number",
          role: "comparison",
          palette_index: 0,
        },
      ],
    });

    expect(svg).toMatch(/stroke-dasharray/);
    expect(svg).not.toContain(THEME.series[1]); // one entity, one hue
  });

  it("breaks the line at a gap instead of dropping it to zero", () => {
    const withGap = draw({
      ...base,
      series: [
        {
          name: "Total calls",
          data: [3, null, 5],
          format: "number",
          role: "primary",
          palette_index: 0,
        },
      ],
    });
    const withZero = draw({
      ...base,
      series: [
        {
          name: "Total calls",
          data: [3, 0, 5],
          format: "number",
          role: "primary",
          palette_index: 0,
        },
      ],
    });
    // A broken line is drawn as two subpaths; a V down to zero is one. If `connectNulls` ever
    // flips, or a null becomes a 0 upstream, these two stop differing.
    expect(withGap).not.toEqual(withZero);
  });

  it("renders an empty result as axes with no marks, not as a crash", () => {
    const svg = draw({
      ...base,
      categories: [],
      series: [
        {
          name: "Total calls",
          data: [],
          format: "number",
          role: "primary",
          palette_index: 0,
        },
      ],
    });

    expect(svg).toContain("<svg");
    // The series still exists — ECharts emits its <path> and its stroke colour — but the path
    // has no geometry. An empty result draws its axes and no line, which is the honest picture.
    expect(geometry(svg, THEME.series[0])).toEqual([""]);
  });

  // Runs last, over everything the charts above drew. A deprecated option is not an error:
  // ECharts logs once and then ignores it, so the chart still draws and merely looks subtly
  // wrong. `grid.containLabel` was exactly that — inert in v6, silently clipping axis labels.
  it("uses no option ECharts has deprecated", () => {
    expect(
      complaints.filter((message) => message.includes("[ECharts]")),
    ).toEqual([]);
  });
});

/** The `d` of every path stroked in `color` — what the reader actually sees drawn. */
function geometry(svg: string, color: string): string[] {
  return [...svg.matchAll(/<path d="([^"]*)"[^>]*stroke="([^"]+)"/g)]
    .filter((match) => match[2] === color)
    .map((match) => match[1]);
}
