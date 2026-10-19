import type { Tone } from "@/platform/components/StatusBadge";
import { formatDate } from "@/platform/format";
import type { Refund } from "./api";

const plural = (n: number, unit: string) => `${n} ${unit}${n === 1 ? "" : "s"}`;

/** How the Reg E deadline reads in the queue and the sheet; null (goodwill) renders as a dash. */
export function deadlineLabel(left: number | null): string {
  if (left === null) return "—";
  if (left < 0) return `Overdue · ${plural(-left, "business day")}`;
  if (left === 0) return "Due today";
  return `${plural(left, "business day")} left`;
}

export function deadlineTone(left: number): Tone {
  if (left <= 0) return "danger";
  if (left <= 2) return "warning";
  return "neutral";
}

export const formatDeadline = (refund: Refund) =>
  refund.deadline_on === null ? "—" : formatDate(refund.deadline_on);
