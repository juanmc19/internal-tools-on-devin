import {
  api,
  qs,
  type HistoryEntry,
  type ListQuery,
  type Page,
} from "@/platform/api";

export type CaseStatus =
  "new" | "in_review" | "recommended" | "approved" | "rejected";
export type Outcome = "approve" | "reject";

export type KycCase = {
  id: number;
  reference: string;
  applicant_name: string;
  date_of_birth: string;
  id_number: string;
  address: string;
  city: string;
  country: string;
  risk: "low" | "medium" | "high";
  screening_result: "clear" | "possible_match" | "match";
  status: CaseStatus;
  assignee_id: string | null;
  recommender_id: string | null;
  recommendation: Outcome | null;
  recommendation_note: string | null;
  decider_id: string | null;
  decision: Outcome | null;
  created_at: string;
  updated_at: string;
  claimed_at: string | null;
  recommended_at: string | null;
  decided_at: string | null;
  version: number;
  masked: boolean;
};

export const APP = "kyc";
export const COUNTRIES = ["MX", "CO", "BR", "AR", "CL", "PE"] as const;
export const STATUSES: CaseStatus[] = [
  "new",
  "in_review",
  "recommended",
  "approved",
  "rejected",
];
export const RISKS = ["low", "medium", "high"] as const;
export const SCREENING = ["clear", "possible_match", "match"] as const;

export const listCases = (query: ListQuery) =>
  api<Page<KycCase>>(`/kyc/cases${qs(query)}`);
export const getCase = (id: number) => api<KycCase>(`/kyc/cases/${id}`);
export const getHistory = (id: number, page = 1) =>
  api<Page<HistoryEntry>>(`/kyc/cases/${id}/history${qs({ page })}`);
export const claimCase = (id: number, version: number) =>
  api<KycCase>(`/kyc/cases/${id}/claim`, { method: "POST", body: { version } });
export const recommendCase = (
  id: number,
  version: number,
  outcome: Outcome,
  note: string,
) =>
  api<KycCase>(`/kyc/cases/${id}/recommend`, {
    method: "POST",
    body: { version, outcome, note },
  });
export const decideCase = (id: number, version: number, outcome: Outcome) =>
  api<KycCase>(`/kyc/cases/${id}/decide`, {
    method: "POST",
    body: { version, outcome },
  });
