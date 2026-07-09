import Link from "next/link";

import { NavLinks } from "@/components/nav-links";
import { ThemeToggle } from "@/components/theme-toggle";

export function TopBar() {
  return (
    <header className="bg-card border-border sticky top-0 z-10 border-b">
      <div className="mx-auto flex h-14 max-w-[1400px] items-center gap-6 px-6">
        <Link
          href="/dashboard"
          className="focus-visible:ring-ring flex items-center gap-2.5 rounded-md focus-visible:ring-2 focus-visible:outline-none"
        >
          <span className="bg-primary size-5 rounded-md" aria-hidden />
          <span className="text-[15px] font-semibold tracking-tight">
            Corelantic
          </span>
        </Link>

        <NavLinks />

        <div className="flex-1" />

        <ThemeToggle />
      </div>
    </header>
  );
}
