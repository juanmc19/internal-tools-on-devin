import { useLocation } from "react-router-dom"
import { Badge } from "@/platform/ui/badge"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/platform/ui/select"
import { personaLabel, usePersona } from "@/platform/persona"
import { APPS } from "@/apps/registry"

export function PersonaSwitcher() {
  const { personas, personaId, switchTo, loading, devMode } = usePersona()
  const { pathname } = useLocation()
  const currentApp = APPS.find((a) => pathname.startsWith(a.path))?.key

  return (
    <div className="flex items-center gap-2" data-testid="persona-switcher">
      <Badge className="rounded-md bg-amber-100 text-amber-900 hover:bg-amber-100" data-testid="dev-only-badge">
        DEV ONLY
      </Badge>
      <Select value={personaId ?? ""} onValueChange={(value) => switchTo(value)} disabled={!devMode || loading}>
        <SelectTrigger className="h-8 w-[300px] text-sm" aria-label="Persona" data-testid="persona-select">
          <SelectValue placeholder={devMode ? (loading ? "Loading personas…" : "Choose a persona") : "Sign-in unavailable"} />
        </SelectTrigger>
        <SelectContent align="end">
          {personas.length === 0 && !loading ? (
            <div className="px-2 py-1.5 text-sm text-muted-foreground">No personas seeded. Run `make seed`.</div>
          ) : null}
          {personas.map((persona) => (
            <SelectItem key={persona.id} value={persona.id} data-testid={`persona-${persona.id}`}>
              {personaLabel(persona, currentApp)}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  )
}
