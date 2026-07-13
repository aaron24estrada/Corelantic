import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { ChartSkeleton } from "@/components/ui/chart-skeleton";
import { Skeleton } from "@/components/ui/skeleton";

const KPI_TILE_COUNT = 5;
const VISUAL_COUNT = 3;

export default function DashboardLoading() {
  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-col gap-2">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-4 w-80" />
      </header>

      {/* The KPI row: five tiles. */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-5">
        {Array.from({ length: KPI_TILE_COUNT }, (_, index) => (
          <Card key={index}>
            <CardContent className="flex flex-col gap-2 pt-1">
              <Skeleton className="h-4 w-20" />
              <Skeleton className="h-7 w-24" />
              <Skeleton className="h-3 w-28" />
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Sized like the charts they precede, so the layout does not jump when data lands. */}
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        {Array.from({ length: VISUAL_COUNT }, (_, index) => (
          <Card
            key={index}
            className={index === 0 ? "lg:col-span-2" : undefined}
          >
            <CardHeader className="gap-2">
              <Skeleton className="h-5 w-32" />
              <Skeleton className="h-4 w-56" />
            </CardHeader>
            <CardContent>
              <ChartSkeleton />
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
