import { describe, expect, it } from "vitest";

import type { components } from "@/lib/api/schema";
import { toEChartsOption } from "@/lib/chart/echarts-option";
import type { ChartTheme } from "@/lib/chart/theme";

type ChartSpec = components["schemas"]["ChartSpec"];

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

function spec(overrides: Partial<ChartSpec> = {}): ChartSpec {
  return {
    type: "line",
    title: "New leads",
    subtitle: "12 Apr 2026 – 10 Jul 2026",
    categories: ["2026-06-01", "2026-06-08"],
    x: { label: "Period", format: null },
    y: { label: "New leads", format: "number" },
    series: [
      {
        name: "New leads",
        data: [400, 480],
        format: "number",
        role: "primary",
        palette_index: 0,
      },
    ],
    ...overrides,
  };
}

// `EChartsCoreOption` is an opaque union of every option every chart type accepts, so it cannot
// be indexed. Narrowing to the handful of keys the adapter sets keeps the assertions typed.
interface DrawnSeries {
  name: string;
  data: (number | null)[];
  color: string;
  type: string;
  connectNulls?: boolean;
  lineStyle?: { type: string; width: number; opacity: number };
  itemStyle?: { color: string; opacity: number };
}

const series = (option: unknown): DrawnSeries[] =>
  (option as { series: DrawnSeries[] }).series;

describe("toEChartsOption", () => {
  it("takes each series' colour from its palette slot, not from its position", () => {
    // The whole colour contract: the API pins a slot to the entity, and the adapter obeys it.
    // Indexing the palette by array position would repaint a filtered chart.
    const option = toEChartsOption(
      spec({
        series: [
          {
            name: "outbound",
            data: [7],
            format: "number",
            role: "primary",
            palette_index: 1,
          },
        ],
      }),
      THEME,
      true,
    );
    expect(series(option)[0].color).toBe(THEME.series[1]);
  });

  it("draws a comparison in its primary's colour, dashed", () => {
    const option = toEChartsOption(
      spec({
        series: [
          {
            name: "New leads",
            data: [400, 480],
            format: "number",
            role: "primary",
            palette_index: 0,
          },
          {
            name: "Previous new leads",
            data: [null, 400],
            format: "number",
            role: "comparison",
            palette_index: 0,
          },
        ],
      }),
      THEME,
      true,
    );
    const [primary, comparison] = series(option);
    expect(comparison.color).toBe(primary.color);
    expect(comparison.lineStyle?.type).toBe("dashed");
    expect(primary.lineStyle?.type).toBe("solid");
  });

  it("breaks the line on a gap rather than plotting a zero", () => {
    const option = toEChartsOption(
      spec({
        series: [
          {
            name: "Voucher rate",
            data: [0.24, null],
            format: "percent",
            role: "primary",
            palette_index: 0,
          },
        ],
      }),
      THEME,
      true,
    );
    expect(series(option)[0].data).toEqual([0.24, null]);
    expect(series(option)[0].connectNulls).toBe(false);
  });

  it("shows a legend for two series and none for one", () => {
    const one = toEChartsOption(spec(), THEME, true) as { legend?: unknown };
    expect(one.legend).toBeUndefined();

    const two = toEChartsOption(
      spec({
        series: [
          {
            name: "inbound",
            data: [3],
            format: "number",
            role: "primary",
            palette_index: 0,
          },
          {
            name: "outbound",
            data: [7],
            format: "number",
            role: "primary",
            palette_index: 1,
          },
        ],
      }),
      THEME,
      true,
    ) as { legend?: { textStyle: { color: string } } };
    // Legend text wears the text token; the swatch beside it carries the identity.
    expect(two.legend?.textStyle.color).toBe(THEME.axis);
  });

  it("formats the y axis from the metric's format, so a rate axis reads as percent", () => {
    const option = toEChartsOption(
      spec({
        y: { label: "Voucher rate %", format: "percent" },
        series: [
          {
            name: "Voucher rate %",
            data: [0.24],
            format: "percent",
            role: "primary",
            palette_index: 0,
          },
        ],
      }),
      THEME,
      true,
    ) as { yAxis: { axisLabel: { formatter: (v: number) => string } } };
    expect(option.yAxis.axisLabel.formatter(0.24)).toBe("24%");
  });

  it("compact mode draws only the primary series, chrome-less", () => {
    // A KPI sparkline is the same spec drawn as a mark: no axes, no legend, and the comparison
    // is dropped — the delta beside the tile already carries the change.
    const option = toEChartsOption(
      spec({
        series: [
          {
            name: "New leads",
            data: [400, 480],
            format: "number",
            role: "primary",
            palette_index: 0,
          },
          {
            name: "Previous",
            data: [null, 400],
            format: "number",
            role: "comparison",
            palette_index: 0,
          },
        ],
      }),
      THEME,
      false,
      true,
    ) as {
      legend?: unknown;
      xAxis: { show: boolean };
      yAxis: { show: boolean };
      series: unknown[];
    };
    expect(option.series).toHaveLength(1);
    expect(option.xAxis.show).toBe(false);
    expect(option.yAxis.show).toBe(false);
    expect(option.legend).toBeUndefined();
  });

  it("honours a reader who asked for less motion", () => {
    expect(
      (toEChartsOption(spec(), THEME, false) as { animation: boolean })
        .animation,
    ).toBe(false);
  });

  it("never hard-codes a colour outside the theme", () => {
    const option = toEChartsOption(
      spec({
        type: "bar",
        categories: ["CTV", "Facebook"],
        series: [
          {
            name: "New leads",
            data: [90, 10],
            format: "number",
            role: "primary",
            palette_index: 0,
          },
        ],
      }),
      THEME,
      true,
    );
    const drawn = series(option)[0];
    expect(drawn.type).toBe("bar");
    expect([...THEME.series]).toContain(drawn.color);
  });
});
