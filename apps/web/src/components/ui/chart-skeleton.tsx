import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

/**
 * The loading shape of a chart, sized like the chart it precedes so the layout does not jump
 * when the data lands. Also what `<Chart>` renders on the server, where there is no canvas.
 */
export function ChartSkeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn("flex h-64 w-full flex-col justify-end gap-2", className)}
      aria-hidden
    >
      <Skeleton className="h-full w-full" />
    </div>
  );
}
