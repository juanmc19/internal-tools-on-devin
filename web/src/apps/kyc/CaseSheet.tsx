import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Eye, EyeOff } from "lucide-react";
import { appendPage, type HistoryEntry, type Page } from "@/platform/api";
import { Button } from "@/platform/ui/button";
import { Badge } from "@/platform/ui/badge";
import { Label } from "@/platform/ui/label";
import { Textarea } from "@/platform/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/platform/ui/select";
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
import { formatDateTime, humanize } from "@/platform/format";
import { usePersona } from "@/platform/persona";
import {
  APP,
  claimCase,
  decideCase,
  getCase,
  getHistory,
  recommendCase,
  type KycCase,
  type Outcome,
} from "./api";
import { CaseStatusBadge, RiskBadge, ScreeningBadge } from "./badges";
import { HISTORY } from "./history";

type Pending = "recommend" | "decide" | null;

export function CaseSheet({
  caseId,
  onOpenChange,
  onChanged,
}: {
  caseId: number | null;
  onOpenChange: (open: boolean) => void;
  onChanged: () => void;
}) {
  const { me, can, nameOf, personaId } = usePersona();
  const [record, setRecord] = useState<KycCase | null>(null);
  const [history, setHistory] = useState<Page<HistoryEntry>>();
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [pending, setPending] = useState<Pending>(null);
  const [outcome, setOutcome] = useState<Outcome>("approve");
  const [note, setNote] = useState("");

  const load = useCallback(async () => {
    if (caseId === null) return;
    setLoading(true);
    try {
      const [detail, hist] = await Promise.all([
        getCase(caseId),
        getHistory(caseId),
      ]);
      setRecord(detail);
      setHistory(hist);
    } catch {
      setRecord(null);
      setHistory({ items: [], total: 0, page: 1, page_size: 0 });
    } finally {
      setLoading(false);
    }
  }, [caseId]);

  const loadMoreHistory = async () => {
    if (caseId === null || !history) return;
    const loaded = history;
    const next = await getHistory(caseId, loaded.page + 1);
    setHistory(appendPage(loaded, next));
  };

  useEffect(() => {
    setRecord(null);
    setHistory(undefined);
    void load();
  }, [load, personaId]);

  const run = async (label: string, action: () => Promise<KycCase>) => {
    setBusy(true);
    try {
      const updated = await action();
      setRecord(updated);
      setPending(null);
      setNote("");
      toast.success(
        `${label}: ${updated.reference} is now ${humanize(updated.status).toLowerCase()}.`,
      );
      onChanged();
      setHistory(await getHistory(updated.id));
    } catch {
      // the API refusal is already on screen as a toast with its code; close the dialog, reload the record
      setPending(null);
      void load();
    } finally {
      setBusy(false);
    }
  };

  const open = caseId !== null;
  const c = record;
  const canClaim = !!c && c.status === "new" && can(APP, "case.claim");
  const canRecommend =
    !!c &&
    c.status === "in_review" &&
    c.assignee_id === me?.id &&
    can(APP, "case.recommend");
  // Decide is shown to every senior reviewer, including the one who recommended: the API enforces SoD.
  const canDecide =
    !!c && c.status === "recommended" && can(APP, "case.decide");
  const selfRecommended = !!c && c.recommender_id === me?.id;

  const actions =
    c && (canClaim || canRecommend || canDecide) ? (
      <>
        {canClaim && (
          <Button
            data-testid="action-claim"
            disabled={busy}
            onClick={() => run("Claimed", () => claimCase(c.id, c.version))}
          >
            Claim
          </Button>
        )}
        {canRecommend && (
          <Button
            data-testid="action-recommend"
            disabled={busy}
            onClick={() => {
              setOutcome("approve");
              setPending("recommend");
            }}
          >
            Recommend…
          </Button>
        )}
        {canDecide && (
          <Button
            data-testid="action-decide"
            disabled={busy}
            onClick={() => {
              setOutcome(c.recommendation ?? "approve");
              setPending("decide");
            }}
          >
            Decide…
          </Button>
        )}
      </>
    ) : c ? (
      <span className="text-sm text-muted-foreground">
        No actions for your role at this stage.
      </span>
    ) : null;

  return (
    <>
      <RecordSheet
        open={open}
        onOpenChange={onOpenChange}
        title={c ? <span className="font-mono">{c.reference}</span> : "Case"}
        description={
          c
            ? `${c.country} · created ${formatDateTime(c.created_at)} · v${c.version}`
            : undefined
        }
        badges={
          c && (
            <>
              <CaseStatusBadge value={c.status} />
              <RiskBadge value={c.risk} />
              <ScreeningBadge value={c.screening_result} />
              <Badge
                variant="outline"
                data-testid="masking-badge"
                className="gap-1 font-normal text-muted-foreground"
              >
                {c.masked ? (
                  <EyeOff className="size-3" />
                ) : (
                  <Eye className="size-3" />
                )}
                {c.masked ? "Masked for your role" : "Unmasked · read audited"}
              </Badge>
            </>
          )
        }
        loading={loading && !c}
        actions={actions}
        history={history?.items}
        historyLoading={history === undefined}
        historyOptions={HISTORY}
        historyTotal={history?.total}
        onLoadMoreHistory={loadMoreHistory}
      >
        {c && (
          <div className="space-y-6">
            <section>
              <h3 className="mb-2 text-xs font-medium tracking-wide text-muted-foreground uppercase">
                Applicant
              </h3>
              <FieldGrid>
                <Field
                  label="Name"
                  value={
                    <span data-testid="field-applicant">
                      {c.applicant_name}
                    </span>
                  }
                  masked={c.masked}
                />
                <Field
                  label="Date of birth"
                  value={c.date_of_birth}
                  masked={c.masked}
                />
                <Field
                  label="ID number"
                  value={<span className="font-mono">{c.id_number}</span>}
                  masked={c.masked}
                />
                <Field label="Address" value={c.address} masked={c.masked} />
                <Field label="City" value={c.city} />
                <Field label="Country" value={c.country} />
                <Field
                  label="Screening"
                  value={<ScreeningBadge value={c.screening_result} />}
                />
              </FieldGrid>
            </section>
            <section>
              <h3 className="mb-2 text-xs font-medium tracking-wide text-muted-foreground uppercase">
                Review
              </h3>
              <FieldGrid>
                <Field
                  label="Assignee"
                  value={c.assignee_id ? nameOf(c.assignee_id) : "—"}
                />
                <Field
                  label="Claimed"
                  value={c.claimed_at ? formatDateTime(c.claimed_at) : "—"}
                />
                <Field
                  label="Recommended by"
                  value={c.recommender_id ? nameOf(c.recommender_id) : "—"}
                />
                <Field
                  label="Recommendation"
                  value={c.recommendation ? humanize(c.recommendation) : "—"}
                />
                <Field
                  label="Decided by"
                  value={c.decider_id ? nameOf(c.decider_id) : "—"}
                />
                <Field
                  label="Decision"
                  value={c.decision ? humanize(c.decision) : "—"}
                />
              </FieldGrid>
              {c.recommendation_note && (
                <p
                  className="mt-3 rounded-md border bg-muted/40 p-3 text-sm"
                  data-testid="recommendation-note"
                >
                  {c.recommendation_note}
                </p>
              )}
            </section>
          </div>
        )}
      </RecordSheet>

      <Dialog
        open={pending !== null}
        onOpenChange={(o) => !o && setPending(null)}
      >
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>
              {pending === "decide" ? "Decide" : "Recommend"} {c?.reference}
            </DialogTitle>
            <DialogDescription>
              {pending === "decide"
                ? `Recommendation: ${c?.recommendation ? humanize(c.recommendation) : "—"} by ${nameOf(c?.recommender_id)}.${selfRecommended ? " You made this recommendation; separation of duties is enforced by the API." : ""}`
                : "Your recommendation goes to a senior reviewer for the decision."}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Outcome</Label>
              <Select
                value={outcome}
                onValueChange={(v) => setOutcome(v as Outcome)}
              >
                <SelectTrigger data-testid="outcome-select" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="approve">Approve</SelectItem>
                  <SelectItem value="reject">Reject</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {pending === "recommend" && (
              <div className="space-y-2">
                <Label htmlFor="note">Note</Label>
                <Textarea
                  id="note"
                  data-testid="recommend-note"
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  rows={3}
                  placeholder="What you checked and why."
                />
              </div>
            )}
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setPending(null)}
              disabled={busy}
            >
              Cancel
            </Button>
            <Button
              data-testid="confirm-action"
              disabled={busy || (pending === "recommend" && !note.trim())}
              onClick={() =>
                c &&
                (pending === "decide"
                  ? run("Decided", () => decideCase(c.id, c.version, outcome))
                  : run("Recommended", () =>
                      recommendCase(c.id, c.version, outcome, note),
                    ))
              }
            >
              {pending === "decide"
                ? "Record decision"
                : "Submit recommendation"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
