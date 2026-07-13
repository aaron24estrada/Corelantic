/**
 * The chart theme, read off the live DOM rather than restated in TypeScript.
 *
 * Canvas takes colours as JS values, but `globals.css` owns the palette — including the eight
 * categorical slots whose ordering is a colourblind-safety property, not a preference. Copying
 * those hexes here would give us two sources of truth and one of them would rot. So we read the
 * custom properties from the element the chart is actually mounted on, which also means the
 * `.dark` class resolves them for free and a theme toggle re-reads the same names.
 *
 * `theme-provider.tsx` exists for exactly this: the theme has to be a value React can observe.
 */

/** The palette has eight slots; `ChartSeries.palette_index` is pinned to `0..7` by the API. */
export const PALETTE_SLOTS = 8;

export interface ChartTheme {
  series: readonly string[];
  axis: string;
  grid: string;
  surface: string;
  text: string;
}

function readVariable(styles: CSSStyleDeclaration, name: string): string {
  const value = styles.getPropertyValue(name).trim();
  if (!value) {
    // A missing token means the chart would draw in transparent-black and look merely "off".
    // Fail loudly at the boundary instead (standards/principles.md).
    throw new Error(
      `chart theme: CSS custom property ${name} resolved to nothing`,
    );
  }
  return value;
}

export function readChartTheme(element: HTMLElement): ChartTheme {
  const styles = getComputedStyle(element);
  return {
    series: Array.from({ length: PALETTE_SLOTS }, (_, slot) =>
      readVariable(styles, `--chart-${slot + 1}`),
    ),
    axis: readVariable(styles, "--muted-foreground"),
    grid: readVariable(styles, "--border"),
    surface: readVariable(styles, "--card"),
    text: readVariable(styles, "--card-foreground"),
  };
}

/** Motion is decoration here; a reader who has asked for less of it gets a static chart. */
export function prefersReducedMotion(): boolean {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}
