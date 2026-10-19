import { useCallback, useEffect, useState } from "react";
import { Plus, Search } from "lucide-react";
import type { Page } from "@/platform/api";
import { Input } from "@/platform/ui/input";
import { Button } from "@/platform/ui/button";
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
import { formatDateTime, humanize } from "@/platform/format";
import { usePersona } from "@/platform/persona";
import {
  APP,
  OPEN_STATUSES,
  REGIONS,
  STATUSES,
  TYPES,
  formatUsd,
  listRefunds,
  type Refund,
} from "./api";
import { DeadlineBadge, RefundStatusBadge, TypeBadge } from "./badges";
import { RefundSheet } from "./RefundSheet";
import { NewRefundDialog } from "./NewRefundDialog";

const ALL = "__all__";
const OPEN = OPEN_STATUSES.join(",");
/** Open the queue on work to do: requested and pending second approval, oldest first. */
const INITIAL: TableState = {
  page: 1,
  pageSize: 50,
  sort: "created_at",
  order: "asc",
};

type Filters = { status: string; type: string; region: string; q: string };
const NO_FILTERS: Filters = { status: OPEN, type: ALL, region: ALL, q: "" };

export function Queue() {
  const { personaId, nameOf, roleIn, can } = usePersona();
  const role = roleIn(APP);
  const [state, setState] = useState<TableState>(INITIAL);
  const [filters, setFilters] = useState<Filters>(NO_FILTERS);
  const [data, setData] = useState<Page<Refund>>();
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<Refund | null>(null);
  const [creating, setCreating] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setData(
        await listRefunds({
          status: filters.status === ALL ? undefined : filters.status,
          type: filters.type === ALL ? undefined : filters.type,
          region: filters.region === ALL ? undefined : filters.region,
          q: filters.q.trim() || undefined,
          page: state.page,
          page_size: state.pageSize,
          sort: state.sort,
          order: state.order,
        }),
      );
    } catch {
      setData({ items: [], total: 0, page: 1, page_size: state.pageSize });
    } finally {
      setLoading(false);
    }
  }, [filters, state]);

  useEffect(() => {
    const handle = setTimeout(load, 150);
    return () => clearTimeout(handle);
  }, [load, personaId, reloadKey]);

  const setFilter = (key: keyof Filters) => (value: string) => {
    setFilters((f) => ({ ...f, [key]: value }));
    setState((s) => ({ ...s, page: 1 }));
  };
  const regions = role?.scope?.length ? role.scope : [...REGIONS];
  const reload = () => setReloadKey((k) => k + 1);

  const columns: Column<Refund>[] = [
    {
      key: "reference",
      header: "Reference",
      sortable: true,
      width: "160px",
      render: (r) => <span className="font-mono text-xs">{r.reference}</span>,
    },
    {
      key: "customer",
      header: "Customer",
      render: (r) => (
        <span className="text-muted-foreground">{r.customer_name}</span>
      ),
    },
    {
      key: "amount_cents",
      header: "Amount",
      sortable: true,
      align: "right",
      width: "120px",
      render: (r) => (
        <span className="tabular-nums">{formatUsd(r.amount_cents)}</span>
      ),
    },
    {
      key: "type",
      header: "Type",
      sortable: true,
      width: "110px",
      render: (r) => <TypeBadge value={r.type} />,
    },
    {
      key: "region",
      header: "Region",
      sortable: true,
      width: "110px",
      render: (r) => humanize(r.region),
    },
    {
      key: "deadline_on",
      header: "Reg E deadline",
      sortable: true,
      width: "200px",
      render: (r) => <DeadlineBadge refund={r} />,
    },
    {
      key: "status",
      header: "Status",
      sortable: true,
      width: "190px",
      render: (r) => <RefundStatusBadge value={r.status} />,
    },
    {
      key: "approvals",
      header: "Approvals",
      width: "100px",
      render: (r) => (
        <span className="text-muted-foreground tabular-nums">
          {r.approvals.length} / {r.approvals_required}
        </span>
      ),
    },
    {
      key: "requester",
      header: "Requested by",
      render: (r) => nameOf(r.requester_id),
    },
    {
      key: "created_at",
      header: "Created",
      sortable: true,
      width: "170px",
      render: (r) => (
        <span className="text-muted-foreground">
          {formatDateTime(r.created_at)}
        </span>
      ),
    },
  ];

  const toolbar = (
    <div
      className="flex flex-wrap items-center gap-2"
      data-testid="refunds-filters"
    >
      <div className="relative">
        <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          data-testid="refunds-search"
          value={filters.q}
          onChange={(e) => setFilter("q")(e.target.value)}
          placeholder="Search reference, e.g. TEST-RFD-000123"
          className="w-72 pl-8"
        />
      </div>
      <FilterSelect
        testId="filter-status"
        value={filters.status}
        onChange={setFilter("status")}
        placeholder="Status"
        options={STATUSES}
        leading={[
          { value: OPEN, label: "Open · requested, pending second approval" },
        ]}
        className="w-72"
      />
      <FilterSelect
        testId="filter-type"
        value={filters.type}
        onChange={setFilter("type")}
        placeholder="Type"
        options={TYPES}
      />
      <FilterSelect
        testId="filter-region"
        value={filters.region}
        onChange={setFilter("region")}
        placeholder="Region"
        options={regions}
      />
      {(filters.q ||
        filters.status !== OPEN ||
        filters.type !== ALL ||
        filters.region !== ALL) && (
        <Button
          variant="ghost"
          size="sm"
          onClick={() => {
            setFilters(NO_FILTERS);
            setState(INITIAL);
          }}
        >
          Clear
        </Button>
      )}
      {can(APP, "refund.request") && (
        <Button
          size="sm"
          className="ml-auto"
          data-testid="new-refund"
          onClick={() => setCreating(true)}
        >
          <Plus className="size-4" />
          New refund
        </Button>
      )}
    </div>
  );

  return (
    <>
      <DataTable
        columns={columns}
        rows={data?.items}
        total={data?.total ?? 0}
        state={state}
        onStateChange={setState}
        rowKey={(r) => r.id}
        rowTestId={(r) => `refunds-row-${r.reference}`}
        loading={loading}
        onRowClick={setSelected}
        selectedKey={selected?.id ?? null}
        toolbar={toolbar}
        emptyTitle="No refunds match"
        emptyDescription="Try another filter or reference, or switch persona: agents only see their regions."
      />
      <RefundSheet
        refundId={selected?.id ?? null}
        onOpenChange={(open) => !open && setSelected(null)}
        onChanged={reload}
      />
      <NewRefundDialog
        open={creating}
        onOpenChange={setCreating}
        regions={regions}
        onCreated={(refund) => {
          setFilters({ ...NO_FILTERS, q: refund.reference });
          setState(INITIAL);
          setSelected(refund);
        }}
      />
    </>
  );
}

function FilterSelect({
  testId,
  value,
  onChange,
  placeholder,
  options,
  leading = [],
  className,
}: {
  testId: string;
  value: string;
  onChange: (v: string) => void;
  placeholder: string;
  options: readonly string[];
  leading?: { value: string; label: string }[];
  className?: string;
}) {
  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger
        data-testid={testId}
        className={className ?? "w-40"}
        size="sm"
      >
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent>
        {leading.map((o) => (
          <SelectItem key={o.value} value={o.value}>
            {o.label}
          </SelectItem>
        ))}
        <SelectItem value={ALL}>All · {placeholder.toLowerCase()}</SelectItem>
        {options.map((o) => (
          <SelectItem key={o} value={o}>
            {humanize(o)}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
