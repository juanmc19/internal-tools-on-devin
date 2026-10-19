import { Badge } from "@/platform/ui/badge"
import { cn } from "@/platform/lib/utils"
import { humanize } from "@/platform/format"

export type Tone = "neutral" | "info" | "success" | "warning" | "danger"

const TONES: Record<Tone, string> = {
  neutral: "border-border bg-muted text-foreground",
  info: "border-blue-200 bg-blue-50 text-blue-700",
  success: "border-emerald-200 bg-emerald-50 text-emerald-700",
  warning: "border-amber-200 bg-amber-50 text-amber-800",
  danger: "border-red-200 bg-red-50 text-red-700",
}

export function StatusBadge({
  value,
  tone = "neutral",
  label,
  className,
}: {
  value: string | null | undefined
  tone?: Tone
  label?: string
  className?: string
}) {
  return (
    <Badge variant="outline" className={cn("rounded-md font-medium", TONES[tone], className)}>
      {label ?? humanize(value)}
    </Badge>
  )
}
