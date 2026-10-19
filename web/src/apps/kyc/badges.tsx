import { StatusBadge, type Tone } from "@/platform/components/StatusBadge";
import type { KycCase } from "./api";

const STATUS_TONE: Record<KycCase["status"], Tone> = {
  new: "neutral",
  in_review: "info",
  recommended: "warning",
  approved: "success",
  rejected: "danger",
};
const RISK_TONE: Record<KycCase["risk"], Tone> = {
  low: "neutral",
  medium: "warning",
  high: "danger",
};
const SCREENING_TONE: Record<KycCase["screening_result"], Tone> = {
  clear: "success",
  possible_match: "warning",
  match: "danger",
};

export const CaseStatusBadge = ({ value }: { value: KycCase["status"] }) => (
  <StatusBadge value={value} tone={STATUS_TONE[value]} />
);
export const RiskBadge = ({ value }: { value: KycCase["risk"] }) => (
  <StatusBadge value={value} tone={RISK_TONE[value]} />
);
export const ScreeningBadge = ({
  value,
}: {
  value: KycCase["screening_result"];
}) => <StatusBadge value={value} tone={SCREENING_TONE[value]} />;
