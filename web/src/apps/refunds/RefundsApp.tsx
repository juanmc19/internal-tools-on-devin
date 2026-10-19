import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { cn } from "@/platform/lib/utils";
import { PageHeader } from "@/platform/shell/PageHeader";
import { AuditView } from "@/platform/components/AuditView";
import { EmptyState } from "@/platform/components/EmptyState";
import { usePersona } from "@/platform/persona";
import { APP } from "./api";
import { Queue } from "./Queue";
import { HISTORY } from "./history";

const REFUND_ACTIONS = [
  "refund.request",
  "refund.approve",
  "refund.reject",
  "refund.pay",
  "security.denied",
  "seed.import",
];

export function RefundsApp() {
  const { can, roleIn, me } = usePersona();
  const role = roleIn(APP);
  const canAudit = can(APP, "audit.read");

  if (me && !role) {
    return (
      <>
        <PageHeader title="Refunds Desk" />
        <EmptyState
          title="No role in Refunds"
          description={`${me.name} has no role in this app. Pick another persona.`}
        />
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="Refunds Desk"
        description="Request, approve and pay card refunds. Two approvers above $5,000; customer names are masked by role; every change is audited."
        actions={
          <nav
            className="flex gap-1 rounded-md border bg-muted/40 p-0.5"
            data-testid="refunds-tabs"
          >
            <Tab to="/refunds" end label="Queue" />
            {canAudit && <Tab to="/refunds/audit" label="Audit log" />}
          </nav>
        }
      />
      <Routes>
        <Route index element={<Queue />} />
        <Route
          path="audit"
          element={
            canAudit ? (
              <AuditView app={APP} actions={REFUND_ACTIONS} options={HISTORY} />
            ) : (
              <Navigate to="/refunds" replace />
            )
          }
        />
        <Route path="*" element={<Navigate to="/refunds" replace />} />
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
