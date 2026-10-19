/* eslint-disable react-refresh/only-export-components -- context, hook and label helper belong together */
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react"
import { api, getPersonaId, setPersonaId, type Me, type RoleInfo } from "@/platform/api"

type PersonaState = {
  personas: Me[]
  personaId: string | null
  me: Me | null
  loading: boolean
  devMode: boolean
  switchTo: (id: string | null) => void
  roleIn: (app: string) => RoleInfo | null
  can: (app: string, permission: string) => boolean
  nameOf: (actorId: string | null | undefined) => string
}

const PersonaContext = createContext<PersonaState | null>(null)

export function PersonaProvider({ children }: { children: ReactNode }) {
  const [personas, setPersonas] = useState<Me[]>([])
  const [personaId, setId] = useState<string | null>(() => getPersonaId())
  const [loading, setLoading] = useState(true)
  const [devMode, setDevMode] = useState(true)

  useEffect(() => {
    let cancelled = false
    api<{ items: Me[] }>("/dev/users", { silent: true })
      .then((body) => {
        if (cancelled) return
        setPersonas(body.items)
        const stored = getPersonaId()
        if (stored && !body.items.some((p) => p.id === stored)) {
          setPersonaId(null)
          setId(null)
        }
      })
      .catch(() => {
        if (!cancelled) setDevMode(false)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const switchTo = useCallback((id: string | null) => {
    setPersonaId(id)
    setId(id)
  }, [])

  const me = useMemo(() => personas.find((p) => p.id === personaId) ?? null, [personas, personaId])

  const value = useMemo<PersonaState>(
    () => ({
      personas,
      personaId,
      me,
      loading,
      devMode,
      switchTo,
      roleIn: (app) => me?.roles.find((r) => r.app === app) ?? null,
      can: (app, permission) => me?.roles.find((r) => r.app === app)?.permissions.includes(permission) ?? false,
      nameOf: (actorId) => {
        if (!actorId) return "System"
        return personas.find((p) => p.id === actorId)?.name ?? actorId
      },
    }),
    [personas, personaId, me, loading, devMode, switchTo],
  )

  return <PersonaContext.Provider value={value}>{children}</PersonaContext.Provider>
}

export function usePersona(): PersonaState {
  const ctx = useContext(PersonaContext)
  if (!ctx) throw new Error("usePersona must be used inside PersonaProvider")
  return ctx
}

export function personaLabel(persona: Me, appKey?: string): string {
  const role = (appKey && persona.roles.find((r) => r.app === appKey)) || persona.roles[0]
  if (!role) return persona.name
  const scope = role.scope.join(", ")
  return `${persona.name} · ${role.role_label} · ${scope}`
}
