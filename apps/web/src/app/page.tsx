import Link from "next/link";

export default function HomePage() {
  return (
    <main className="mx-auto flex min-h-dvh max-w-xl flex-col items-center justify-center gap-4 px-6 text-center">
      <h1 className="text-3xl font-semibold tracking-tight">Corelantic</h1>
      <p className="text-muted-foreground text-balance">
        See your dashboard and ask your data in natural language — one place,
        one sign-in.
      </p>
      <Link
        href="/dashboard"
        className="border-border rounded-lg border px-4 py-2 text-sm font-medium"
      >
        Open dashboard
      </Link>
    </main>
  );
}
