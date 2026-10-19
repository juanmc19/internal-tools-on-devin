import { StatusBadge, type Tone } from "@/platform/components/StatusBadge";
import type { Refund } from "./api";

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
