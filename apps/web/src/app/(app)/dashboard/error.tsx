"use client";

import { ErrorState } from "@/components/ui/error-state";

/**
 * The route's error boundary. Next requires a client component here and hands it `reset`, which
 * is the retry `ErrorState` asks for — so a failed dashboard load is recoverable without a
 * full page reload, and never a blank screen or an endless skeleton (standards/nextjs.md).
 */
export default function DashboardError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <ErrorState
      title="The dashboard didn't load"
      // `error.message` is scrubbed to a digest in production, so it is never a leak channel.
      detail={error.message || "Something went wrong while loading this page."}
      onRetry={reset}
    />
  );
}
