import type { HistoryOptions } from "@/platform/components/diff";

/** How Refunds audit entries read in the refund sheet and the audit log. */
export const HISTORY: HistoryOptions = {
  actions: {
    "refund.request": "Requested",
    "refund.approve": "Approved",
    "refund.reject": "Rejected",
    "refund.pay": "Marked paid",
    "seed.import": "Imported by seed",
  },
  lines: {
    status: "Status: {from} → {to}",
    approvals: "Approvals: {value}",
    requester_id: "Requested by {to}",
    rejecter_id: "Rejected by {to}",
    amount_cents: "Amount (cents): {value}",
    type: "Type: {value}",
    region: "Region: {value}",
    customer_name: "Customer name recorded (masked in the audit log)",
    card_last4: "Card last 4 recorded (masked in the audit log)",
    reason: "Reason recorded (masked in the audit log)",
    count: "{value} refunds",
    full_history: "{value} with full history",
  },
  fields: {
    customer_name: "customer name",
    card_last4: "card last 4",
  },
};
