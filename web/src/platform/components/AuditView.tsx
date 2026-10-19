import { useCallback, useEffect, useState } from "react";
import { ShieldCheck, ShieldX } from "lucide-react";
import {
  api,
  qs,
  type AuditEntry,
  type Page,
  type VerifyResult,
} from "@/platform/api";
import { Button } from "@/platform/ui/button";
import { Input } from "@/platform/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/platform/ui/select";
import {
  DataTable,
  type Column,
  type TableState,
} from "@/platform/components/DataTable";
import { summarizeDiff, type HistoryOptions } from "@/platform/components/diff";
import { StatusBadge } from "@/platform/components/StatusBadge";
import { actionLabel, formatDateTime, formatInt } from "@/platform/format";
import { usePersona } from "@/platform/persona";

const ALL = "__all__";

export function AuditView({
  app,
  actions,
  options,
}: {
  app: string;
  actions?: string[];
  options?: HistoryOptions;
}) {
  const { personaId, nameOf } = usePersona();
  const diffOptions: HistoryOptions = {
    resolve: (value) => nameOf(value),
    ...options,
  };
  const labelOf = (action: string) =>
    action === "security.denied"
      ? "Refused"
      : (options?.actions?.[action] ?? actionLabel(action));
  const [state, setState] = useState<TableState>({
    page: 1,
    pageSize: 50,
    sort: "id",
    order: "desc",
  });
  const [recordId, setRecordId] = useState("");
  const [action, setAction] = useState(ALL);
  const [data, setData] = useState<Page<AuditEntry>>();
  const [loading, setLoading] = useState(true);
  const [verify, setVerify] = useState<VerifyResult | null>(null);
  const [verifying, setVerifying] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const page = await api<Page<AuditEntry>>(
        `/audit${qs({
          app,
          record_id: recordId.trim() || undefined,
          action: action === ALL ? undefined : action,
          page: state.page,
          page_size: state.pageSize,
          sort: state.sort,
          order: state.order,
        })}`,
      );
      setData(page);
    } catch {
      setData({ items: [], total: 0, page: 1, page_size: state.pageSize });
    } finally {
      setLoading(false);
    }
  }, [app, recordId, action, state]);

  useEffect(() => {
    const handle = setTimeout(load, 150);
    return () => clearTimeout(handle);
  }, [load, personaId]);

  const runVerify = async () => {
    setVerifying(true);
    try {
      setVerify(await api<VerifyResult>(`/audit/verify${qs({ app })}`));
    } catch {
      setVerify(null);
    } finally {
      setVerifying(false);
    }
  };

  const columns: Column<AuditEntry>[] = [
    {
      key: "id",
      header: "#",
      width: "64px",
      sortable: true,
      render: (e) => <span className="tabular-nums">{e.id}</span>,
    },
    {
      key: "ts",
      header: "Time",
      width: "170px",
      sortable: true,
      render: (e) => (
        <span className="tabular-nums">{formatDateTime(e.ts)}</span>
      ),
    },
    {
      key: "action",
      header: "Action",
      width: "170px",
      sortable: true,
      render: (e) =>
        e.action === "security.denied" ? (
          <StatusBadge
            value={String(e.diff.code ?? "denied")}
            tone="danger"
            label={`Refused · ${String(e.diff.code ?? "")}`}
          />
        ) : (
          labelOf(e.action)
        ),
    },
    {
      key: "actor",
      header: "Actor",
      width: "160px",
      render: (e) => nameOf(e.actor_id),
    },
    {
      key: "record",
      header: "Record",
      width: "170px",
      render: (e) => (
        <span className="font-mono text-xs">{e.record_id ?? "—"}</span>
      ),
    },
    {
      key: "diff",
      header: "Change",
      render: (e) => (
        <span
          className="text-muted-foreground"
          title={summarizeDiff(e.diff, diffOptions).join("\n")}
        >
          {e.action === "security.denied"
            ? "No change"
            : summarizeDiff(e.diff, diffOptions).join(" · ") || "—"}
        </span>
      ),
    },
    {
      key: "hash",
      header: "Hash",
      width: "110px",
      render: (e) => (
        <span className="font-mono text-xs text-muted-foreground">
          {e.hash.slice(0, 10)}
        </span>
      ),
    },
  ];

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <Input
          placeholder="Filter by record reference"
          value={recordId}
          onChange={(e) => {
            setRecordId(e.target.value);
            setState((s) => ({ ...s, page: 1 }));
          }}
          className="w-64"
          aria-label="Record reference"
        />
        <Select
          value={action}
          onValueChange={(value) => {
            setAction(value);
            setState((s) => ({ ...s, page: 1 }));
          }}
        >
          <SelectTrigger className="w-52" aria-label="Action">
            <SelectValue placeholder="All actions" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>All actions</SelectItem>
            {(actions ?? []).map((a) => (
              <SelectItem key={a} value={a}>
                {labelOf(a)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <div className="ml-auto flex items-center gap-2">
          {verify ? (
            verify.ok ? (
              <span
                data-testid="verify-result"
                className="inline-flex items-center gap-1.5 text-sm text-emerald-700"
              >
                <ShieldCheck className="size-4" /> Chain intact ·{" "}
                {formatInt(verify.entries)} entries
              </span>
            ) : (
              <span
                data-testid="verify-result"
                className="inline-flex items-center gap-1.5 text-sm text-red-700"
              >
                <ShieldX className="size-4" /> Chain broken at entry #
                {verify.first_bad_id} ({verify.reason})
              </span>
            )
          ) : null}
          <Button
            variant="outline"
            size="sm"
            onClick={runVerify}
            disabled={verifying}
            data-testid="verify-chain"
          >
            {verifying ? "Verifying…" : "Verify chain"}
          </Button>
        </div>
      </div>
      <DataTable
        columns={columns}
        rows={data?.items}
        total={data?.total ?? 0}
        state={state}
        onStateChange={setState}
        rowKey={(e) => e.id}
        loading={loading}
        emptyTitle="No audit entries"
        emptyDescription="Entries appear here as soon as a record changes."
      />
    </div>
  );
}
