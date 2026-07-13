"use client";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface ErrorStateProps {
  title: string;
  detail: string;
  /**
   * The vocabulary that would have worked, straight from the API's 422 body.
   *
   * Every intent the engine refuses comes back with this list, which is the whole reason the
   * refusal is useful: the agent repairs its intent from it, and a person reads what they could
   * have asked instead of the word "failed".
   */
  allowed?: string[] | null;
  onRetry?: () => void;
  className?: string;
}

export function ErrorState({
  title,
  detail,
  allowed,
  onRetry,
  className,
}: ErrorStateProps) {
  return (
    <div
      role="alert"
      className={cn(
        "border-border bg-card flex flex-col items-start gap-3 rounded-xl border border-dashed p-6",
        className,
      )}
    >
      <div className="flex flex-col gap-1">
        <p className="text-sm font-medium">{title}</p>
        <p className="text-muted-foreground text-sm">{detail}</p>
      </div>

      {allowed && allowed.length > 0 ? (
        <div className="flex flex-col gap-1.5">
          <p className="text-muted-foreground text-xs">
            Try one of these instead:
          </p>
          <ul className="flex flex-wrap gap-1.5">
            {allowed.map((option) => (
              <li
                key={option}
                className="bg-muted text-muted-foreground rounded-full px-2 py-0.5 text-xs font-medium"
              >
                {option}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {onRetry ? (
        <Button size="sm" onClick={onRetry}>
          Try again
        </Button>
      ) : null}
    </div>
  );
}
