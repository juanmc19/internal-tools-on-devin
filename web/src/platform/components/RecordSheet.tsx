import type { ReactNode } from "react";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/platform/ui/sheet";
import { Separator } from "@/platform/ui/separator";
import { Skeleton } from "@/platform/ui/skeleton";
import { HistoryTimeline } from "@/platform/components/HistoryTimeline";
import type { HistoryOptions } from "@/platform/components/diff";
import type { AuditEntry } from "@/platform/api";

export function RecordSheet({
  open,
  onOpenChange,
  title,
  description,
  badges,
  loading,
  children,
  actions,
  history,
  historyLoading,
  historyOptions,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: ReactNode;
  description?: ReactNode;
  badges?: ReactNode;
  loading?: boolean;
  children: ReactNode;
  actions?: ReactNode;
  history?: AuditEntry[];
  historyLoading?: boolean;
  historyOptions?: HistoryOptions;
}) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        className="flex w-full flex-col gap-0 overflow-y-auto p-0 sm:max-w-xl"
        data-testid="record-sheet"
      >
        <SheetHeader className="gap-1 border-b px-6 py-4">
          <SheetTitle className="pr-8 font-mono text-base whitespace-nowrap">
            {title}
          </SheetTitle>
          {badges ? (
            <div className="flex flex-wrap items-center gap-1.5">{badges}</div>
          ) : null}
          {description ? (
            <SheetDescription>{description}</SheetDescription>
          ) : (
            <SheetDescription className="sr-only">
              Record detail
            </SheetDescription>
          )}
        </SheetHeader>
        <div className="flex-1 px-6 py-4">
          {loading ? (
            <div className="space-y-3">
              <Skeleton className="h-4 w-1/2" />
              <Skeleton className="h-4 w-2/3" />
              <Skeleton className="h-4 w-1/3" />
            </div>
          ) : (
            children
          )}
        </div>
        {actions ? (
          <>
            <Separator />
            <div
              className="flex flex-wrap items-center gap-2 px-6 py-3"
              data-testid="record-actions"
            >
              {actions}
            </div>
          </>
        ) : null}
        {history !== undefined || historyLoading ? (
          <>
            <Separator />
            <section className="px-6 py-4">
              <h3 className="mb-3 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                History
              </h3>
              <HistoryTimeline
                entries={history}
                loading={historyLoading}
                options={historyOptions}
              />
            </section>
          </>
        ) : null}
      </SheetContent>
    </Sheet>
  );
}

export function Field({
  label,
  value,
  masked,
}: {
  label: string;
  value: ReactNode;
  masked?: boolean;
}) {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-xs text-muted-foreground">
        {label}
        {masked ? (
          <span className="ml-1 text-[10px] uppercase tracking-wide text-amber-700">
            masked
          </span>
        ) : null}
      </dt>
      <dd className="text-sm">{value ?? "—"}</dd>
    </div>
  );
}

export function FieldGrid({ children }: { children: ReactNode }) {
  return <dl className="grid grid-cols-2 gap-x-6 gap-y-3">{children}</dl>;
}
