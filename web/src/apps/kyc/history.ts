import type { HistoryOptions } from "@/platform/components/diff";

/** How KYC audit entries read in the case sheet and the audit log. */
export const HISTORY: HistoryOptions = {
  actions: {
    "case.claim": "Claimed",
    "case.recommend": "Recommended",
    "case.decide": "Decided",
    "case.read_unmasked": "Viewed unmasked",
    "seed.import": "Imported by seed",
  },
  lines: {
    assignee_id: "Assigned to {to}",
    status: "Status: {from} → {to}",
    recommendation: "Recommendation: {to}",
    recommendation_note: "Note added (not recorded in the audit log)",
    decision: "Decision: {to}",
    fields: "Viewed unmasked: {value}",
    count: "{value} cases",
    full_history: "{value} with full history",
  },
  fields: {
    applicant_name: "name",
    date_of_birth: "date of birth",
    id_number: "ID number",
    address: "address",
  },
};
