import { humanize } from "@/platform/format"

/** Turns an audit diff like {status: {from: "new", to: "in_review"}} into readable lines. */
export function summarizeDiff(diff: Record<string, unknown>): string[] {
  const lines: string[] = []
  for (const [field, change] of Object.entries(diff)) {
    if (change && typeof change === "object" && !Array.isArray(change)) {
      const c = change as Record<string, unknown>
      if ("from" in c || "to" in c) {
        lines.push(`${humanize(field)}: ${display(c.from)} → ${display(c.to)}`)
        continue
      }
      if (c.changed === true) {
        lines.push(`${humanize(field)}: changed (masked)`)
        continue
      }
    }
    lines.push(`${humanize(field)}: ${display(change)}`)
  }
  return lines
}

function display(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—"
  if (typeof value === "string") return /^[a-z_]+$/.test(value) ? humanize(value) : value
  return String(value)
}
