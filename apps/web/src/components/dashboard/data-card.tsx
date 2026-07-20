import type { ReactNode } from "react";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import type { components } from "@/lib/api/schema";

type ErrorResponse = components["schemas"]["ErrorResponse"];

interface DataCardProps {
  title: string;
  description?: string;
  error?: ErrorResponse;
  isEmpty: boolean;
  emptyDetail: string;
  children: ReactNode;
}

/**
 * One card, one question — and the one place loading, empty and refused are handled, so no
 * visual can forget them. `ErrorState` renders the 422's `allowed` list, so a refusal names the
 * vocabulary that would have worked instead of just failing.
 */
export function DataCard({
  title,
  description,
  error,
  isEmpty,
  emptyDetail,
  children,
}: DataCardProps) {
  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        {description ? <CardDescription>{description}</CardDescription> : null}
      </CardHeader>
      <CardContent>
        {error ? (
          <ErrorState
            title="Can’t draw this"
            detail={error.detail}
            allowed={error.allowed}
          />
        ) : isEmpty ? (
          <EmptyState title="Nothing to show" detail={emptyDetail} />
        ) : (
          children
        )}
      </CardContent>
    </Card>
  );
}
