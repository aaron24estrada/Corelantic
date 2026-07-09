import { TopBar } from "@/components/top-bar";

// Everything inside this group is the signed-in product surface. When Entra
// lands (issue #21), the session check goes here and redirects when absent —
// which is why the shell is a route group and not part of the root layout.
export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-dvh flex-col">
      <TopBar />
      <main className="mx-auto w-full max-w-[1400px] flex-1 px-6 py-8">
        {children}
      </main>
    </div>
  );
}
