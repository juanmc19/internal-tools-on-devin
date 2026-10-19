import { useCallback, useEffect, useState } from "react";
import { Search } from "lucide-react";
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
  COUNTRIES,
  RISKS,
  SCREENING,
  STATUSES,
  listCases,
  type KycCase,
} from "./api";
import { CaseStatusBadge, RiskBadge, ScreeningBadge } from "./badges";
import { CaseSheet } from "./CaseSheet";

const ALL = "__all__";
const OPEN = "new,in_review,recommended";
/** Open the queue on work to do: open cases, oldest first. Every status is one click away in the filter. */
const INITIAL: TableState = {
  page: 1,
  pageSize: 50,
  sort: "created_at",
  order: "asc",
};

type Filters = {
  status: string;
  country: string;
  risk: string;
  screening_result: string;
  q: string;
};
const NO_FILTERS: Filters = {
  status: OPEN,
  country: ALL,
  risk: ALL,
  screening_result: ALL,
  q: "",
};

export function Queue() {
  const { personaId, nameOf, roleIn } = usePersona();
  const role = roleIn(APP);
  const [state, setState] = useState<TableState>(INITIAL);
  const [filters, setFilters] = useState<Filters>(NO_FILTERS);
  const [data, setData] = useState<Page<KycCase>>();
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<KycCase | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setData(
        await listCases({
          status: filters.status === ALL ? undefined : filters.status,
          country: filters.country === ALL ? undefined : filters.country,
          risk: filters.risk === ALL ? undefined : filters.risk,
          screening_result:
            filters.screening_result === ALL
              ? undefined
              : filters.screening_result,
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
  const countries = role?.scope?.length ? role.scope : [...COUNTRIES];

  const columns: Column<KycCase>[] = [
    {
      key: "reference",
      header: "Reference",
      sortable: true,
      width: "160px",
      render: (c) => <span className="font-mono text-xs">{c.reference}</span>,
    },
    {
      key: "applicant",
      header: "Applicant",
      render: (c) => (
        <span className="text-muted-foreground">{c.applicant_name}</span>
      ),
    },
    {
      key: "country",
      header: "Country",
      sortable: true,
      width: "90px",
      render: (c) => c.country,
    },
    {
      key: "risk",
      header: "Risk",
      sortable: true,
      width: "110px",
      render: (c) => <RiskBadge value={c.risk} />,
    },
    {
      key: "screening_result",
      header: "Screening",
      sortable: true,
      width: "140px",
      render: (c) => <ScreeningBadge value={c.screening_result} />,
    },
    {
      key: "status",
      header: "Status",
      sortable: true,
      width: "130px",
      render: (c) => <CaseStatusBadge value={c.status} />,
    },
    {
      key: "assignee",
      header: "Assignee",
      render: (c) =>
        c.assignee_id ? (
          nameOf(c.assignee_id)
        ) : (
          <span className="text-muted-foreground">—</span>
        ),
    },
    {
      key: "updated_at",
      header: "Updated",
      sortable: true,
      width: "170px",
      render: (c) => (
        <span className="text-muted-foreground">
          {formatDateTime(c.updated_at)}
        </span>
      ),
    },
  ];

  const toolbar = (
    <div
      className="flex flex-wrap items-center gap-2"
      data-testid="kyc-filters"
    >
      <div className="relative">
        <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          data-testid="kyc-search"
          value={filters.q}
          onChange={(e) => setFilter("q")(e.target.value)}
          placeholder="Search reference, e.g. TEST-KYC-000123"
          className="w-72 pl-8"
        />
      </div>
      <FilterSelect
        testId="filter-status"
        value={filters.status}
        onChange={setFilter("status")}
        placeholder="Status"
        options={STATUSES}
        leading={[{ value: OPEN, label: "Open · new, in review, recommended" }]}
      />
      <FilterSelect
        testId="filter-country"
        value={filters.country}
        onChange={setFilter("country")}
        placeholder="Country"
        options={countries}
      />
      <FilterSelect
        testId="filter-risk"
        value={filters.risk}
        onChange={setFilter("risk")}
        placeholder="Risk"
        options={[...RISKS]}
      />
      <FilterSelect
        testId="filter-screening"
        value={filters.screening_result}
        onChange={setFilter("screening_result")}
        placeholder="Screening"
        options={[...SCREENING]}
      />
      {(filters.q ||
        filters.status !== OPEN ||
        [filters.country, filters.risk, filters.screening_result].some(
          (v) => v !== ALL,
        )) && (
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
        rowKey={(c) => c.id}
        rowTestId={(c) => `kyc-row-${c.reference}`}
        loading={loading}
        onRowClick={setSelected}
        selectedKey={selected?.id ?? null}
        toolbar={toolbar}
        emptyTitle="No cases match"
        emptyDescription="Try another filter or reference, or switch persona: analysts only see their countries."
      />
      <CaseSheet
        caseId={selected?.id ?? null}
        onOpenChange={(open) => !open && setSelected(null)}
        onChanged={() => setReloadKey((k) => k + 1)}
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
}: {
  testId: string;
  value: string;
  onChange: (v: string) => void;
  placeholder: string;
  options: readonly string[];
  leading?: { value: string; label: string }[];
}) {
  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger data-testid={testId} className="w-40" size="sm">
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
