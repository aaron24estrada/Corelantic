import Link from "next/link";

import { NavLinks } from "@/components/nav-links";
import { ThemeToggle } from "@/components/theme-toggle";

// A translucent, blurred bar over a centred column — the shell reads as a curated report, not
// app chrome. The sidebar returns when "Ask your data" and multi-page land (docs O-4 / E4).
export function TopBar() {
  return (
    <header className="bg-background/80 border-border sticky top-0 z-20 border-b backdrop-blur-xl backdrop-saturate-150">
      <div className="mx-auto flex h-15 max-w-[1200px] items-center gap-6 px-6 lg:px-10">
        <Link
          href="/dashboard"
          className="focus-visible:ring-ring flex items-center gap-2.5 rounded-md focus-visible:ring-2 focus-visible:outline-none"
        >
          <span className="bg-primary grid size-[26px] place-items-center rounded-lg text-[14px] font-extrabold tracking-tight text-white">
            C
          </span>
          <span className="text-[15px] font-semibold tracking-tight">
            Corelantic{" "}
            <span className="text-muted-foreground font-normal">· KRW</span>
          </span>
        </Link>

        <NavLinks />

        <div className="flex-1" />

        <span className="text-muted-foreground hidden items-center gap-2 text-xs md:flex">
          <span className="bg-chart-8 ring-chart-8/25 size-1.5 rounded-full ring-3" />
          Live · gold_tspot
        </span>
        <ThemeToggle />
      </div>
    </header>
  );
}
