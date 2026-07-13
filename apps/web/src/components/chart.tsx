"use client";

import { BarChart, LineChart } from "echarts/charts";
import {
  GridComponent,
  LegendComponent,
  TooltipComponent,
} from "echarts/components";
import * as echarts from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { useTheme } from "next-themes";
import { useEffect, useRef } from "react";

import type { components } from "@/lib/api/schema";
import { toEChartsOption } from "@/lib/chart/echarts-option";
import { prefersReducedMotion, readChartTheme } from "@/lib/chart/theme";
import { cn } from "@/lib/utils";

type ChartSpec = components["schemas"]["ChartSpec"];

// Registered once, explicitly, rather than importing the `echarts` barrel: this is what keeps a
// two-chart dashboard from shipping the map, gauge and tree renderers it never draws. A new
// visual type registers its chart here and extends `ChartSpec` — it does not add a component.
echarts.use([
  LineChart,
  BarChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  CanvasRenderer,
]);

interface ChartProps {
  spec: ChartSpec;
  /** Charts have no intrinsic height; a canvas with none collapses to nothing. */
  className?: string;
}

/**
 * Every chart in the product — a dashboard visual or an agent's answer — renders through here.
 *
 * `echarts/core` directly, not `echarts-for-react`: a wrapper would be a second vendor to trust
 * for React 19 support, and the whole point of the `ChartSpec` seam is that exactly one file
 * knows the library. That file is `lib/chart/echarts-option.ts`; this one just owns the canvas.
 */
export function Chart({ spec, className }: ChartProps) {
  const container = useRef<HTMLDivElement>(null);
  const { resolvedTheme } = useTheme();

  useEffect(() => {
    const element = container.current;
    if (!element) return;

    const instance = echarts.init(element, undefined, { renderer: "canvas" });
    // Read the palette off the mounted element, so the `.dark` class resolves it and CSS stays
    // the single source of truth. `resolvedTheme` is in the dep array to re-read on a toggle.
    instance.setOption(
      toEChartsOption(spec, readChartTheme(element), !prefersReducedMotion()),
    );

    // ECharts sizes to its container once. Without this a chart drawn in a collapsed tab, or a
    // sidebar opening beside it, keeps the width it was born with.
    const observer = new ResizeObserver(() => instance.resize());
    observer.observe(element);

    return () => {
      observer.disconnect();
      instance.dispose();
    };
  }, [spec, resolvedTheme]);

  return (
    <div
      ref={container}
      className={cn("h-64 w-full", className)}
      role="img"
      aria-label={
        spec.subtitle ? `${spec.title}, ${spec.subtitle}` : spec.title
      }
    />
  );
}
