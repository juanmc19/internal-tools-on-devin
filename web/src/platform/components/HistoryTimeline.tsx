import { useState } from "react";
import type { HistoryEntry } from "@/platform/api";
import { actionLabel, formatDateTime } from "@/platform/format";
import { summarizeDiff, type HistoryOptions } from "@/platform/components/diff";
import { usePersona } from "@/platform/persona";
import { Button } from "@/platform/ui/button";
import { Skeleton } from "@/platform/ui/skeleton";
import { cn } from "@/platform/lib/utils";

export function HistoryTimeline({
  entries,
  loading,
  className,
  options,
  total,
  onLoadMore,
}: {
  entries: HistoryEntry[] | undefined;
  loading?: boolean;
  className?: string;
  options?: HistoryOptions;
  /** Exact number of entries on the server; with `onLoadMore`, a button fetches the next page. */
  total?: number;
  onLoadMore?: () => Promise<void>;
}) {
  const { nameOf } = usePersona();
  const [loadingMore, setLoadingMore] = useState(false);
  const diffOptions: HistoryOptions = {
    resolve: (value) => nameOf(value),
    ...options,
  };
  if (loading && !entries) {
    return (
      <div className={cn("space-y-3", className)}>
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-10 w-full" />
        ))}
      </div>
    );
  }
  if (!entries || entries.length === 0) {
    return (
      <p className={cn("text-sm text-muted-foreground", className)}>
        No history yet.
      </p>
    );
  }
  const hasMore =
    onLoadMore !== undefined && total !== undefined && entries.length < total;
  const loadMore = async () => {
    if (!onLoadMore) return;
    setLoadingMore(true);
    try {
      await onLoadMore();
    } finally {
      setLoadingMore(false);
    }
  };
  return (
    <div className={className}>
      <ol
        className="relative space-y-0 border-l pl-4"
        data-testid="history-timeline"
      >
        {entries.map((entry) => {
          const denied = entry.action === "security.denied";
          return (
            <li key={entry.id} className="relative pb-4 last:pb-0">
              <span
                className={cn(
                  "absolute -left-[21px] top-1.5 size-2.5 rounded-full border-2 border-background",
                  denied ? "bg-red-500" : "bg-primary",
                )}
              />
              <div className="flex items-baseline justify-between gap-3">
                <p className="text-sm font-medium">
                  {denied
                    ? `Refused · ${String(entry.diff.code ?? "")}`
                    : (options?.actions?.[entry.action] ??
                      actionLabel(entry.action))}
                </p>
                <time className="shrink-0 text-xs tabular-nums text-muted-foreground">
                  {formatDateTime(entry.ts)}
                </time>
              </div>
              <p className="text-xs text-muted-foreground">
                {nameOf(entry.actor_id)}
              </p>
              {!denied
                ? summarizeDiff(entry.diff, diffOptions).map((line) => (
                    <p key={line} className="text-xs text-muted-foreground">
                      {line}
                    </p>
                  ))
                : null}
            </li>
          );
        })}
      </ol>
      {hasMore ? (
        <Button
          variant="outline"
          size="sm"
          className="mt-3"
          disabled={loadingMore}
          onClick={() => void loadMore()}
          data-testid="history-load-more"
        >
          Load more ({entries.length} of {total} shown)
        </Button>
      ) : null}
    </div>
  );
}
