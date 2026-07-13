import { cn } from "@/lib/utils";

interface EmptyStateProps {
  title: string;
  detail: string;
  className?: string;
}

/**
 * A query that succeeded and returned nothing.
 *
 * Distinct from `ErrorState` on purpose: "no leads in this window" is an answer, and dressing it
 * as a failure teaches the reader to distrust an empty chart that is telling the truth.
 */
export function EmptyState({ title, detail, className }: EmptyStateProps) {
  return (
    <div
      className={cn(
        "border-border flex flex-col items-center justify-center gap-1 rounded-xl border border-dashed p-8 text-center",
        className,
      )}
    >
      <p className="text-sm font-medium">{title}</p>
      <p className="text-muted-foreground max-w-xs text-sm">{detail}</p>
    </div>
  );
}
