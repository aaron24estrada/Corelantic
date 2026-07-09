import Link from "next/link";

import { Button } from "@/components/ui/button";

// The unauthenticated entry. Entra sign-in replaces the link with a sign-in
// button when F1 lands (issue #21); until then it is the way in.
export default function HomePage() {
  return (
    <main className="mx-auto flex min-h-dvh max-w-xl flex-col items-center justify-center gap-5 px-6 text-center">
      <span className="bg-primary size-9 rounded-lg" aria-hidden />
      <h1 className="text-[40px] leading-none font-semibold tracking-tight">
        Corelantic
      </h1>
      <p className="text-muted-foreground text-balance">
        See your dashboard and ask your data in natural language — one place,
        one sign-in.
      </p>
      <Button size="lg" asChild>
        <Link href="/dashboard">Open dashboard</Link>
      </Button>
    </main>
  );
}
