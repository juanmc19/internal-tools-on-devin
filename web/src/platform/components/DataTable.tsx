import type { ReactNode } from "react"
import { ArrowDown, ArrowUp, ArrowUpDown, ChevronLeft, ChevronRight } from "lucide-react"
import { Button } from "@/platform/ui/button"
import { Skeleton } from "@/platform/ui/skeleton"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/platform/ui/table"
import { cn } from "@/platform/lib/utils"
import { formatRange } from "@/platform/format"
import { EmptyState } from "@/platform/components/EmptyState"

export type SortOrder = "asc" | "desc"

export type TableState = { page: number; pageSize: number; sort: string; order: SortOrder }

export type Column<T> = {
  key: string
  header: string
  sortable?: boolean
  width?: string
  align?: "left" | "right"
  render: (row: T) => ReactNode
}

type Props<T> = {
  columns: Column<T>[]
  rows: T[] | undefined
  total: number
  state: TableState
  onStateChange: (next: TableState) => void
  rowKey: (row: T) => string | number
  loading?: boolean
  onRowClick?: (row: T) => void
  selectedKey?: string | number | null
  emptyTitle?: string
  emptyDescription?: string
  toolbar?: ReactNode
  rowTestId?: (row: T) => string
}

export function DataTable<T>({
  columns,
  rows,
  total,
  state,
  onStateChange,
  rowKey,
  loading,
  onRowClick,
  selectedKey,
  emptyTitle = "Nothing here",
  emptyDescription,
  toolbar,
  rowTestId,
}: Props<T>) {
  const pageCount = Math.max(1, Math.ceil(total / state.pageSize))
  const showSkeleton = loading && !rows
  const isEmpty = !loading && rows !== undefined && rows.length === 0

  const toggleSort = (column: Column<T>) => {
    if (!column.sortable) return
    const order: SortOrder = state.sort === column.key && state.order === "asc" ? "desc" : "asc"
    onStateChange({ ...state, page: 1, sort: column.key, order })
  }

  return (
    <div className="flex flex-col rounded-lg border bg-card">
      {toolbar ? <div className="flex flex-wrap items-center gap-2 border-b px-3 py-2">{toolbar}</div> : null}
      <div className="relative overflow-x-auto">
        <Table className="table-fixed">
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              {columns.map((column) => (
                <TableHead
                  key={column.key}
                  style={column.width ? { width: column.width } : undefined}
                  className={cn(
                    "h-9 text-xs font-medium text-muted-foreground",
                    column.align === "right" && "text-right",
                    column.sortable && "cursor-pointer select-none hover:text-foreground",
                  )}
                  onClick={() => toggleSort(column)}
                  aria-sort={
                    state.sort === column.key ? (state.order === "asc" ? "ascending" : "descending") : undefined
                  }
                >
                  <span className="inline-flex items-center gap-1">
                    {column.header}
                    {column.sortable ? (
                      state.sort === column.key ? (
                        state.order === "asc" ? (
                          <ArrowUp className="size-3" />
                        ) : (
                          <ArrowDown className="size-3" />
                        )
                      ) : (
                        <ArrowUpDown className="size-3 opacity-40" />
                      )
                    ) : null}
                  </span>
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody className={cn(loading && rows && "opacity-60 transition-opacity")}>
            {showSkeleton
              ? Array.from({ length: 10 }).map((_, i) => (
                  <TableRow key={i}>
                    {columns.map((column) => (
                      <TableCell key={column.key} className="py-2.5">
                        <Skeleton className="h-4 w-3/4" />
                      </TableCell>
                    ))}
                  </TableRow>
                ))
              : rows?.map((row) => {
                  const key = rowKey(row)
                  return (
                    <TableRow
                      key={key}
                      data-testid={rowTestId?.(row)}
                      data-state={selectedKey === key ? "selected" : undefined}
                      className={cn(onRowClick && "cursor-pointer")}
                      onClick={onRowClick ? () => onRowClick(row) : undefined}
                    >
                      {columns.map((column) => (
                        <TableCell
                          key={column.key}
                          className={cn("truncate py-2 text-sm", column.align === "right" && "text-right tabular-nums")}
                        >
                          {column.render(row)}
                        </TableCell>
                      ))}
                    </TableRow>
                  )
                })}
          </TableBody>
        </Table>
        {isEmpty ? <EmptyState title={emptyTitle} description={emptyDescription} /> : null}
      </div>
      <div className="flex items-center justify-between border-t px-3 py-2 text-xs text-muted-foreground">
        <span data-testid="table-range" className="tabular-nums">
          {showSkeleton ? "Loading…" : formatRange(state.page, state.pageSize, total)}
        </span>
        <div className="flex items-center gap-1">
          <span className="mr-2 tabular-nums">
            Page {state.page} of {pageCount.toLocaleString("en-US")}
          </span>
          <Button
            variant="outline"
            size="icon-sm"
            aria-label="Previous page"
            disabled={state.page <= 1 || loading}
            onClick={() => onStateChange({ ...state, page: state.page - 1 })}
          >
            <ChevronLeft />
          </Button>
          <Button
            variant="outline"
            size="icon-sm"
            aria-label="Next page"
            disabled={state.page >= pageCount || loading}
            onClick={() => onStateChange({ ...state, page: state.page + 1 })}
          >
            <ChevronRight />
          </Button>
        </div>
      </div>
    </div>
  )
}
