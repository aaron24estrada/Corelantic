import { Card, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

const PLACEHOLDER_CARD_COUNT = 6;

export default function DashboardLoading() {
  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-col gap-2">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-4 w-80" />
      </header>

      <ul className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: PLACEHOLDER_CARD_COUNT }, (_, index) => (
          <li key={index}>
            <Card>
              <CardHeader className="gap-2">
                <Skeleton className="h-5 w-2/5" />
                <Skeleton className="h-4 w-4/5" />
              </CardHeader>
            </Card>
          </li>
        ))}
      </ul>
    </div>
  );
}
