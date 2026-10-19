import { useState, type FormEvent } from "react";
import { toast } from "sonner";
import { Button } from "@/platform/ui/button";
import { Input } from "@/platform/ui/input";
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
import { humanize } from "@/platform/format";
import { TYPES, createRefund, type Refund, type RefundType } from "./api";

type Form = {
  customer_name: string;
  card_last4: string;
  amount: string;
  type: RefundType;
  reported_on: string;
  region: string;
  reason: string;
};

const EMPTY = (region: string): Form => ({
  customer_name: "",
  card_last4: "",
  amount: "",
  type: "goodwill",
  reported_on: "",
  region,
  reason: "",
});

/** Only the last 4 digits ever leave the browser; the field refuses anything longer. */
export function NewRefundDialog({
  open,
  onOpenChange,
  regions,
  onCreated,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  regions: readonly string[];
  onCreated: (refund: Refund) => void;
}) {
  const [form, setForm] = useState<Form>(() => EMPTY(regions[0] ?? ""));
  const [busy, setBusy] = useState(false);
  const set = <K extends keyof Form>(key: K, value: Form[K]) =>
    setForm((f) => ({ ...f, [key]: value }));

  const amountCents = Math.round(Number(form.amount) * 100);
  const valid =
    form.customer_name.trim() &&
    /^\d{4}$/.test(form.card_last4) &&
    Number.isFinite(amountCents) &&
    amountCents > 0 &&
    form.region &&
    form.reason.trim() &&
    (form.type !== "dispute" || form.reported_on);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!valid) return;
    setBusy(true);
    try {
      const refund = await createRefund({
        customer_name: form.customer_name.trim(),
        card_last4: form.card_last4,
        amount_cents: amountCents,
        type: form.type,
        reason: form.reason.trim(),
        reported_on: form.type === "dispute" ? form.reported_on : null,
        region: form.region,
      });
      toast.success(`Requested ${refund.reference}.`);
      setForm(EMPTY(regions[0] ?? ""));
      onOpenChange(false);
      onCreated(refund);
    } catch {
      // the API refusal is already on screen as a toast with its code
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <form onSubmit={submit} className="space-y-4">
          <DialogHeader>
            <DialogTitle>New refund</DialogTitle>
            <DialogDescription>
              Enter only the last 4 digits of the card. Refunds above $5,000
              need two approvers.
            </DialogDescription>
          </DialogHeader>
          <div className="grid grid-cols-2 gap-4">
            <div className="col-span-2 space-y-2">
              <Label htmlFor="new-customer">Customer name</Label>
              <Input
                id="new-customer"
                data-testid="new-customer"
                value={form.customer_name}
                onChange={(e) => set("customer_name", e.target.value)}
                maxLength={120}
                autoFocus
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="new-last4">Card last 4</Label>
              <Input
                id="new-last4"
                data-testid="new-last4"
                inputMode="numeric"
                placeholder="4242"
                value={form.card_last4}
                onChange={(e) =>
                  set(
                    "card_last4",
                    e.target.value.replace(/\D/g, "").slice(0, 4),
                  )
                }
                maxLength={4}
                className="font-mono"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="new-amount">Amount (USD)</Label>
              <Input
                id="new-amount"
                data-testid="new-amount"
                type="number"
                min="0.01"
                step="0.01"
                placeholder="0.00"
                value={form.amount}
                onChange={(e) => set("amount", e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label>Type</Label>
              <Select
                value={form.type}
                onValueChange={(v) => set("type", v as RefundType)}
              >
                <SelectTrigger data-testid="new-type" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {TYPES.map((t) => (
                    <SelectItem key={t} value={t}>
                      {humanize(t)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Region</Label>
              <Select
                value={form.region}
                onValueChange={(v) => set("region", v)}
              >
                <SelectTrigger data-testid="new-region" className="w-full">
                  <SelectValue placeholder="Region" />
                </SelectTrigger>
                <SelectContent>
                  {regions.map((r) => (
                    <SelectItem key={r} value={r}>
                      {humanize(r)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            {form.type === "dispute" && (
              <div className="col-span-2 space-y-2">
                <Label htmlFor="new-reported">
                  Date the customer reported it
                </Label>
                <Input
                  id="new-reported"
                  data-testid="new-reported"
                  type="date"
                  value={form.reported_on}
                  onChange={(e) => set("reported_on", e.target.value)}
                />
                <p className="text-xs text-muted-foreground">
                  Within the last 2 years, and not in the future.
                </p>
              </div>
            )}
            <div className="col-span-2 space-y-2">
              <Label htmlFor="new-reason">Reason</Label>
              <Textarea
                id="new-reason"
                data-testid="new-reason"
                rows={3}
                value={form.reason}
                onChange={(e) => set("reason", e.target.value)}
                placeholder="What happened and why a refund is due."
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={busy}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              data-testid="new-submit"
              disabled={busy || !valid}
            >
              Request refund
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
