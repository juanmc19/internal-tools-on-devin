import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Check, Clock, Eye, EyeOff } from "lucide-react";
import type { AuditEntry } from "@/platform/api";
import { Button } from "@/platform/ui/button";
import { Badge } from "@/platform/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/platform/ui/dialog";
import {
  Field,
  FieldGrid,
  RecordSheet,
} from "@/platform/components/RecordSheet";
import { formatDate, formatDateTime, humanize } from "@/platform/format";
import { usePersona } from "@/platform/persona";
import {
  APP,
  approveRefund,
  formatUsd,
  getHistory,
  getRefund,
  payRefund,
  rejectRefund,
  type Refund,
} from "./api";
import { DeadlineBadge, RefundStatusBadge, TypeBadge } from "./badges";
import { formatDeadline } from "./deadline";
import { HISTORY } from "./history";

export function RefundSheet({
  refundId,
  onOpenChange,
  onChanged,
}: {
  refundId: number | null;
  onOpenChange: (open: boolean) => void;
  onChanged: () => void;
}) {
  const { me, can, nameOf, personaId } = usePersona();
  const [record, setRecord] = useState<Refund | null>(null);
  const [history, setHistory] = useState<AuditEntry[]>();
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [confirmReject, setConfirmReject] = useState(false);

  const load = useCallback(async () => {
    if (refundId === null) return;
    setLoading(true);
    try {
      const [detail, hist] = await Promise.all([
        getRefund(refundId),
        getHistory(refundId),
      ]);
      setRecord(detail);
      setHistory(hist.items);
    } catch {
      setRecord(null);
      setHistory([]);
    } finally {
      setLoading(false);
    }
  }, [refundId]);

  useEffect(() => {
    setRecord(null);
    setHistory(undefined);
    void load();
  }, [load, personaId]);

  const run = async (label: string, action: () => Promise<Refund>) => {
    setBusy(true);
    try {
      const updated = await action();
      setRecord(updated);
      setConfirmReject(false);
      toast.success(
        `${label}: ${updated.reference} is now ${humanize(updated.status).toLowerCase()}.`,
      );
      onChanged();
      setHistory((await getHistory(updated.id)).items);
    } catch {
      // the API refusal is already on screen as a toast with its code; reload the record
      setConfirmReject(false);
      void load();
    } finally {
      setBusy(false);
    }
  };

  const open = refundId !== null;
  const r = record;
  const isOpen =
    !!r && (r.status === "requested" || r.status === "pending_second_approval");
  // Approve is shown to every approver, including the requester and anyone who already approved:
  // the API enforces separation of duties and the refusal is visible as a toast.
  const canApprove = isOpen && can(APP, "refund.approve");
  const canReject = isOpen && can(APP, "refund.reject");
  const canPay = !!r && r.status === "approved" && can(APP, "refund.pay");
  const selfRequested = !!r && r.requester_id === me?.id;
  const alreadyApproved =
    !!r && r.approvals.some((a) => a.approver_id === me?.id);

  const actions =
    r && (canApprove || canReject || canPay) ? (
      <>
        {canApprove && (
          <Button
            data-testid="action-approve"
            disabled={busy}
            onClick={() =>
              run("Approved", () => approveRefund(r.id, r.version))
            }
          >
            Approve
          </Button>
        )}
        {canReject && (
          <Button
            data-testid="action-reject"
            variant="outline"
            disabled={busy}
            onClick={() => setConfirmReject(true)}
          >
            Reject…
          </Button>
        )}
        {canPay && (
          <Button
            data-testid="action-pay"
            disabled={busy}
            onClick={() => run("Paid", () => payRefund(r.id, r.version))}
          >
            Mark paid
          </Button>
        )}
      </>
    ) : r ? (
      <span className="text-sm text-muted-foreground">
        No actions for your role at this stage.
      </span>
    ) : null;

  return (
    <>
      <RecordSheet
        open={open}
        onOpenChange={onOpenChange}
        title={r ? <span className="font-mono">{r.reference}</span> : "Refund"}
        description={
          r
            ? `${humanize(r.region)} · requested ${formatDateTime(r.created_at)} · v${r.version}`
            : undefined
        }
        badges={
          r && (
            <>
              <RefundStatusBadge value={r.status} />
              <TypeBadge value={r.type} />
              <Badge
                variant="outline"
                data-testid="masking-badge"
                className="gap-1 font-normal text-muted-foreground"
              >
                {r.masked ? (
                  <EyeOff className="size-3" />
                ) : (
                  <Eye className="size-3" />
                )}
                {r.masked ? "Masked for your role" : "Unmasked"}
              </Badge>
            </>
          )
        }
        loading={loading && !r}
        actions={actions}
        history={history}
        historyLoading={history === undefined}
        historyOptions={HISTORY}
      >
        {r && (
          <div className="space-y-6">
            <section>
              <h3 className="mb-2 text-xs font-medium tracking-wide text-muted-foreground uppercase">
                Refund
              </h3>
              <FieldGrid>
                <Field
                  label="Amount"
                  value={
                    <span
                      className="text-base font-semibold tabular-nums"
                      data-testid="field-amount"
                    >
                      {formatUsd(r.amount_cents)}
                    </span>
                  }
                />
                <Field
                  label="Approvals required"
                  value={
                    <span data-testid="field-approvals-required">
                      {r.approvals_required}
                      {r.approvals_required > 1 && (
                        <span className="ml-1 text-xs text-muted-foreground">
                          (above $5,000)
                        </span>
                      )}
                    </span>
                  }
                />
                <Field label="Type" value={<TypeBadge value={r.type} />} />
                <Field
                  label="Reported by customer"
                  value={r.type === "dispute" ? formatDate(r.reported_on) : "—"}
                />
                <Field
                  label="Reg E deadline"
                  value={
                    <span
                      className="inline-flex flex-wrap items-center gap-2"
                      data-testid="field-deadline"
                    >
                      {r.type === "dispute" && <span>{formatDeadline(r)}</span>}
                      <DeadlineBadge refund={r} />
                    </span>
                  }
                />
                <Field label="Region" value={humanize(r.region)} />
                <Field label="Requested by" value={nameOf(r.requester_id)} />
              </FieldGrid>
              <p
                className="mt-3 rounded-md border bg-muted/40 p-3 text-sm"
                data-testid="field-reason"
              >
                {r.reason}
              </p>
            </section>
            <section>
              <h3 className="mb-2 text-xs font-medium tracking-wide text-muted-foreground uppercase">
                Customer
              </h3>
              <FieldGrid>
                <Field
                  label="Name"
                  value={
                    <span data-testid="field-customer">{r.customer_name}</span>
                  }
                  masked={r.masked}
                />
                <Field
                  label="Card"
                  value={
                    <span className="font-mono" data-testid="field-card">
                      •••• {r.card_last4}
                    </span>
                  }
                />
              </FieldGrid>
            </section>
            <section>
              <h3 className="mb-2 text-xs font-medium tracking-wide text-muted-foreground uppercase">
                Approvals
              </h3>
              <ol className="space-y-2" data-testid="approvals-timeline">
                {r.approvals.map((a, i) => (
                  <li
                    key={a.approver_id + a.approved_at}
                    className="flex items-center gap-2 text-sm"
                  >
                    <Check className="size-4 text-emerald-600" />
                    <span>
                      {i + 1} of {r.approvals_required} ·{" "}
                      {nameOf(a.approver_id)}
                    </span>
                    <span className="text-muted-foreground">
                      {formatDateTime(a.approved_at)}
                    </span>
                  </li>
                ))}
                {r.status !== "rejected" &&
                  Array.from(
                    {
                      length: Math.max(
                        0,
                        r.approvals_required - r.approvals.length,
                      ),
                    },
                    (_, i) => (
                      <li
                        key={`pending-${i}`}
                        className="flex items-center gap-2 text-sm text-muted-foreground"
                      >
                        <Clock className="size-4" />
                        {r.approvals.length + i + 1} of {r.approvals_required} ·
                        awaiting a different approver
                      </li>
                    ),
                  )}
                {r.status === "rejected" && (
                  <li className="text-sm text-muted-foreground">
                    Rejected by {nameOf(r.rejecter_id)} ·{" "}
                    {formatDateTime(r.rejected_at)}
                  </li>
                )}
                {r.paid_at && (
                  <li className="flex items-center gap-2 text-sm">
                    <Check className="size-4 text-emerald-600" />
                    Paid · {formatDateTime(r.paid_at)}
                  </li>
                )}
              </ol>
              {(selfRequested || alreadyApproved) && canApprove && (
                <p
                  className="mt-3 text-xs text-muted-foreground"
                  data-testid="sod-hint"
                >
                  {selfRequested
                    ? "You requested this refund; the API enforces separation of duties on Approve."
                    : "You already approved this refund; a second approval must come from someone else."}
                </p>
              )}
            </section>
          </div>
        )}
      </RecordSheet>

      <Dialog
        open={confirmReject}
        onOpenChange={(o) => !o && setConfirmReject(false)}
      >
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Reject {r?.reference}</DialogTitle>
            <DialogDescription>
              {r &&
                `${formatUsd(r.amount_cents)} ${r.type} refund. Rejecting is final; no money moves.`}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setConfirmReject(false)}
              disabled={busy}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              data-testid="confirm-reject"
              disabled={busy}
              onClick={() =>
                r && run("Rejected", () => rejectRefund(r.id, r.version))
              }
            >
              Reject refund
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
