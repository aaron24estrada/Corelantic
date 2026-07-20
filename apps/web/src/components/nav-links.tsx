"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

// Overview is the only route that exists today. The rest show the product's shape and stay
// inert until their routes land ("Ask your data" with the NL panel, #19), so they cannot 404.
const ROUTES = [{ href: "/dashboard", label: "Overview" }] as const;
const PLANNED: { label: string; soon?: boolean }[] = [
  { label: "Leads & intake" },
  { label: "Call center" },
  { label: "Ask your data", soon: true },
];

export function NavLinks() {
  const pathname = usePathname();

  return (
    <nav className="flex items-center gap-0.5">
      {ROUTES.map(({ href, label }) => {
        const isActive = pathname === href || pathname.startsWith(`${href}/`);
        return (
          <Link
            key={href}
            href={href}
            aria-current={isActive ? "page" : undefined}
            className={cn(
              "rounded-lg px-3 py-1.5 text-sm transition-colors",
              "focus-visible:ring-ring focus-visible:ring-2 focus-visible:outline-none",
              isActive
                ? "text-foreground font-semibold"
                : "text-muted-foreground hover:text-foreground hover:bg-muted font-medium",
            )}
          >
            {label}
          </Link>
        );
      })}
      {PLANNED.map(({ label, soon }) => (
        <span
          key={label}
          aria-disabled="true"
          className="text-muted-foreground/70 hidden cursor-default items-center gap-1.5 px-3 py-1.5 text-sm font-medium lg:inline-flex"
        >
          {label}
          {soon ? (
            <span className="border-border text-muted-foreground rounded-full border px-1.5 py-px text-[9px] font-bold tracking-wide uppercase">
              soon
            </span>
          ) : null}
        </span>
      ))}
    </nav>
  );
}
