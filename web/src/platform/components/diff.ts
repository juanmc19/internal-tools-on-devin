import { humanize } from "@/platform/format";

/** How an app wants its audit diffs read out. Everything is optional; the defaults humanize the raw keys. */
export type DiffOptions = {
  /** Per diff key: a plain label ("Status") or a template with {from}, {to} or {value} ("Assigned to {to}"). */
  lines?: Record<string, string>;
  /** Names for field keys that appear inside values, e.g. {"applicant_name": "name"}. */
  fields?: Record<string, string>;
  /** Resolves ids inside values to display names (actor ids → persona names). */
  resolve?: (value: string) => string;
};

export type HistoryOptions = DiffOptions & {
  /** Per action: label shown as the entry title, e.g. {"case.claim": "Claimed"}. */
  actions?: Record<string, string>;
};

/** Turns an audit diff like {status: {from: "new", to: "in_review"}} into readable lines. */
export function summarizeDiff(
  diff: Record<string, unknown>,
  options: DiffOptions = {},
): string[] {
  const lines: string[] = [];
  const show = (value: unknown) => display(value, options);
  for (const [field, change] of Object.entries(diff)) {
    const template = options.lines?.[field];
    const label =
      template && !template.includes("{") ? template : humanize(field);
    if (change && typeof change === "object" && !Array.isArray(change)) {
      const c = change as Record<string, unknown>;
      if ("from" in c || "to" in c) {
        lines.push(
          template?.includes("{")
            ? fill(template, {
                from: show(c.from),
                to: show(c.to),
                value: show(c.to),
              })
            : `${label}: ${show(c.from)} → ${show(c.to)}`,
        );
        continue;
      }
      if (c.changed === true) {
        lines.push(
          template
            ? fill(template, { from: "—", to: "—", value: "changed" })
            : `${label}: changed (masked)`,
        );
        continue;
      }
    }
    lines.push(
      template?.includes("{")
        ? fill(template, { from: "—", to: show(change), value: show(change) })
        : `${label}: ${show(change)}`,
    );
  }
  return lines;
}

function fill(template: string, values: Record<string, string>): string {
  return template.replace(
    /\{(from|to|value)\}/g,
    (_, key: string) => values[key] ?? "—",
  );
}

function display(value: unknown, options: DiffOptions): string {
  if (value === null || value === undefined || value === "") return "—";
  if (Array.isArray(value))
    return value.map((v) => fieldName(String(v), options)).join(", ");
  if (typeof value === "string") {
    const resolved = options.resolve?.(value) ?? value;
    if (resolved !== value) return resolved;
    return /^[a-z_]+$/.test(value) ? humanize(value) : value;
  }
  return String(value);
}

function fieldName(key: string, options: DiffOptions): string {
  return options.fields?.[key] ?? humanize(key).toLowerCase();
}
