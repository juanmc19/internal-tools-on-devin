import { StatusBadge, type Tone } from "@/platform/components/StatusBadge";
import type { Refund } from "./api";
import { deadlineLabel, deadlineTone } from "./deadline";

const STATUS_TONE: Record<Refund["status"], Tone> = {
  requested: "neutral",
  pending_second_approval: "warning",
  approved: "info",
  paid: "success",
  rejected: "danger",
};
const TYPE_TONE: Record<Refund["type"], Tone> = {
  goodwill: "neutral",
  dispute: "warning",
};

export const RefundStatusBadge = ({ value }: { value: Refund["status"] }) => (
  <StatusBadge value={value} tone={STATUS_TONE[value]} />
);
export const TypeBadge = ({ value }: { value: Refund["type"] }) => (
  <StatusBadge value={value} tone={TYPE_TONE[value]} />
);

/** Red when overdue or due today, amber within 2 business days, otherwise plain; goodwill shows a dash. */
export function DeadlineBadge({ refund }: { refund: Refund }) {
  const left = refund.business_days_left;
  if (left === null || refund.deadline_on === null) {
    return (
      <span className="text-muted-foreground" data-testid="deadline-none">
        —
      </span>
    );
  }
  return (
    <span data-testid={left < 0 ? "deadline-overdue" : "deadline"}>
      <StatusBadge
        value={null}
        label={deadlineLabel(left)}
        tone={deadlineTone(left)}
        className="tabular-nums"
      />
    </span>
  );
}
