export function formatInt(value: number): string {
  return value.toLocaleString("en-US")
}

export function formatRange(page: number, pageSize: number, total: number): string {
  if (total === 0) return "0 of 0"
  const start = (page - 1) * pageSize + 1
  const end = Math.min(page * pageSize, total)
  return `${formatInt(start)}–${formatInt(end)} of ${formatInt(total)}`
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString("en-GB", {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  })
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—"
  if (value.includes("\u2022")) return value
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleDateString("en-GB", { year: "numeric", month: "short", day: "2-digit" })
}

/** "in_review" -> "In review"; "SOD_VIOLATION" stays as is (codes are shown verbatim). */
export function humanize(value: string | null | undefined): string {
  if (!value) return "—"
  const text = value.replace(/[_.]/g, " ").trim()
  return text.charAt(0).toUpperCase() + text.slice(1)
}

export function actionLabel(action: string): string {
  const [, verb = action] = action.split(".", 2)
  return humanize(verb)
}
