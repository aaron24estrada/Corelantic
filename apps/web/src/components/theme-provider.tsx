"use client";

import { ThemeProvider as NextThemesProvider } from "next-themes";

// The only client component at the root. It exists because the theme has to be a
// value React can read, not just a CSS media query: charts render to canvas and
// take colors as JS, so <Chart> will depend on `useTheme().resolvedTheme` (D2).
// A media-query-only theme could not be overridden by the user, and could not be
// observed by a canvas. Children pass straight through and stay Server Components.
export function ThemeProvider({ children }: { children: React.ReactNode }) {
  return (
    <NextThemesProvider
      attribute="class"
      defaultTheme="system"
      enableSystem
      disableTransitionOnChange
    >
      {children}
    </NextThemesProvider>
  );
}
