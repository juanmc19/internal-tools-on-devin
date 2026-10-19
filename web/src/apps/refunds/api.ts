import {
  api,
  qs,
  type HistoryEntry,
  type ListQuery,
  type Page,
} from "@/platform/api";

export type RefundStatus =
  "requested" | "pending_second_approval" | "approved" | "paid" | "rejected";
export type RefundType = "goodwill" | "dispute";
export type Approval = { approver_id: string; approved_at: string };

export type Refund = {
  id: number;
  reference: string;
  customer_name: string;
  card_last4: string;
  amount_cents: number;
  type: RefundType;
  reason: string;
  reported_on: string | null;
  deadline_on: string | null;
  /** Business days until the Reg E deadline: 0 is due today, negative is overdue, null for goodwill. */
  business_days_left: number | null;
  region: string;
  status: RefundStatus;
  requester_id: string;
  rejecter_id: string | null;
  created_at: string;
  updated_at: string;
  approved_at: string | null;
  paid_at: string | null;
  rejected_at: string | null;
  version: number;
  approvals: Approval[];
  approvals_required: number;
  masked: boolean;
};

export type NewRefund = {
  customer_name: string;
  card_last4: string;
  amount_cents: number;
  type: RefundType;
  reason: string;
  reported_on: string | null;
  region: string;
};

export const APP = "refunds";
export const REGIONS = ["northeast", "southeast", "midwest", "west"] as const;
export const TYPES: RefundType[] = ["goodwill", "dispute"];
export const STATUSES: RefundStatus[] = [
  "requested",
  "pending_second_approval",
  "approved",
  "paid",
  "rejected",
];
export const OPEN_STATUSES: RefundStatus[] = [
  "requested",
  "pending_second_approval",
];

export const formatUsd = (cents: number) =>
  (cents / 100).toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
  });

export const listRefunds = (query: ListQuery) =>
  api<Page<Refund>>(`/refunds${qs(query)}`);
export const getRefund = (id: number) => api<Refund>(`/refunds/${id}`);
export const getHistory = (id: number) =>
  api<{ items: HistoryEntry[]; total: number }>(`/refunds/${id}/history`);
export const createRefund = (body: NewRefund) =>
  api<Refund>("/refunds", { method: "POST", body });
export const approveRefund = (id: number, version: number) =>
  api<Refund>(`/refunds/${id}/approve`, { method: "POST", body: { version } });
export const rejectRefund = (id: number, version: number) =>
  api<Refund>(`/refunds/${id}/reject`, { method: "POST", body: { version } });
export const payRefund = (id: number, version: number) =>
  api<Refund>(`/refunds/${id}/pay`, { method: "POST", body: { version } });
