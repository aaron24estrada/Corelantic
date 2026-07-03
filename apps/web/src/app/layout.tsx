import type { Metadata } from "next";

import "./globals.css";

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
    <html lang="en">
      <body className="bg-background text-foreground min-h-dvh font-sans antialiased">
        {children}
      </body>
    </html>
  );
}
