import type { Metadata } from "next";
import { Open_Sans } from "next/font/google";
import localFont from "next/font/local";

import { ThemeProvider } from "@/components/theme-provider";

import "./globals.css";

const openSans = Open_Sans({
  subsets: ["latin"],
  variable: "--font-open-sans",
  display: "swap",
});

// Bricolage Grotesque — a display grotesque with real character in its digits, used only for
// headline figures (the hero total, the stat-band values). Self-hosted so the private surface
// never calls a font CDN; the two weights ship as woff2 under app/fonts.
const bricolage = localFont({
  src: [
    { path: "./fonts/BricolageGrotesque-SemiBold.woff2", weight: "600", style: "normal" },
    { path: "./fonts/BricolageGrotesque-Bold.woff2", weight: "700", style: "normal" },
  ],
  variable: "--font-bricolage",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Corelantic",
  description: "Sign in once — see your dashboard and ask your data.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    // next-themes writes the resolved theme onto <html> before paint, which the
    // server cannot predict. suppressHydrationWarning scopes that known mismatch
    // to this element instead of silencing it for the whole tree.
    <html
      lang="en"
      className={`${openSans.variable} ${bricolage.variable}`}
      suppressHydrationWarning
    >
      <body className="bg-background text-foreground min-h-dvh font-sans antialiased">
        <ThemeProvider>{children}</ThemeProvider>
      </body>
    </html>
  );
}
