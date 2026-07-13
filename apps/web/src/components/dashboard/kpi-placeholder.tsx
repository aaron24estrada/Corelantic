import { Card, CardContent } from "@/components/ui/card";

/**
 * A KPI tile whose metric is not yet reachable — Spend and ROAS, until `marketing_budget`
 * finishes landing in the readable schema (#37). Shown rather than hidden so the row keeps the
 * shape of the KRW dashboard it mirrors, and says plainly what is missing instead of a zero that
 * reads as real.
 */
export function KpiPlaceholder({
  label,
  note,
}: {
  label: string;
  note: string;
}) {
  return (
    <Card className="border-dashed">
      <CardContent className="flex flex-col gap-1 pt-1">
        <p className="text-muted-foreground text-sm font-medium">{label}</p>
        <p className="text-muted-foreground/60 text-2xl font-semibold tracking-tight">
          —
        </p>
        <p className="text-muted-foreground/80 text-xs">{note}</p>
      </CardContent>
    </Card>
  );
}
