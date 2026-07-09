import type { Metadata } from "next";
import { Open_Sans } from "next/font/google";

import { ThemeProvider } from "@/components/theme-provider";

import "./globals.css";

const openSans = Open_Sans({
  subsets: ["latin"],
  variable: "--font-open-sans",
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
    <html lang="en" className={openSans.variable} suppressHydrationWarning>
      <body className="bg-background text-foreground min-h-dvh font-sans antialiased">
        <ThemeProvider>{children}</ThemeProvider>
      </body>
    </html>
  );
}
