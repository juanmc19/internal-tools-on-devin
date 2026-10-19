import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { cn } from "@/platform/lib/utils";
import { PageHeader } from "@/platform/shell/PageHeader";
import { AuditView } from "@/platform/components/AuditView";
import { EmptyState } from "@/platform/components/EmptyState";
import { usePersona } from "@/platform/persona";
import { APP } from "./api";
import { Queue } from "./Queue";
import { HISTORY } from "./history";

const KYC_ACTIONS = [
  "case.claim",
  "case.recommend",
  "case.decide",
  "case.read_unmasked",
  "security.denied",
  "seed.import",
];

export function KycApp() {
  const { can, roleIn, me } = usePersona();
  const role = roleIn(APP);
  const canAudit = can(APP, "audit.read");

  if (me && !role) {
    return (
      <>
        <PageHeader title="KYC Review Queue" />
        <EmptyState
          title="No role in KYC"
          description={`${me.name} has no role in this app. Pick another persona.`}
        />
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="KYC Review Queue"
        description="Claim, recommend and decide onboarding cases. Applicant data is masked by role; every change is audited."
        actions={
          <nav
            className="flex gap-1 rounded-md border bg-muted/40 p-0.5"
            data-testid="kyc-tabs"
          >
            <Tab to="/kyc" end label="Queue" />
            {canAudit && <Tab to="/kyc/audit" label="Audit log" />}
          </nav>
        }
      />
      <Routes>
        <Route index element={<Queue />} />
        <Route
          path="audit"
          element={
            canAudit ? (
              <AuditView app={APP} actions={KYC_ACTIONS} options={HISTORY} />
            ) : (
              <Navigate to="/kyc" replace />
            )
          }
        />
        <Route path="*" element={<Navigate to="/kyc" replace />} />
      </Routes>
    </>
  );
}

function Tab({ to, label, end }: { to: string; label: string; end?: boolean }) {
  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) =>
        cn(
          "rounded px-3 py-1 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground",
          isActive && "bg-background text-foreground shadow-sm",
        )
      }
    >
      {label}
    </NavLink>
  );
}
