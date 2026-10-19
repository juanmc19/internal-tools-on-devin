import { toast } from "sonner"

export const API_BASE = import.meta.env.VITE_API_BASE ?? "/api"

const PERSONA_KEY = "dev-user"

export function getPersonaId(): string | null {
  return window.localStorage.getItem(PERSONA_KEY)
}

export function setPersonaId(id: string | null) {
  if (id) window.localStorage.setItem(PERSONA_KEY, id)
  else window.localStorage.removeItem(PERSONA_KEY)
}

export class ApiError extends Error {
  code: string
  status: number
  constructor(status: number, code: string, message: string) {
    super(message)
    this.status = status
    this.code = code
  }
}

export type Page<T> = { items: T[]; total: number; page: number; page_size: number }

/** Adds the next page's items to the ones already loaded (for "Load more" lists such as a record's history). */
export function appendPage<T>(loaded: Page<T>, next: Page<T>): Page<T> {
  return { ...next, items: [...loaded.items, ...next.items] }
}

export type RoleInfo = {
  app: string
  app_name: string
  role: string
  role_label: string
  permissions: string[]
  masked: boolean
  scope: string[]
}

export type Me = { id: string; name: string; roles: RoleInfo[] }

export type HealthApp = {
  key: string
  name: string
  owner_team: string
  description: string
  web_path: string
  status: string
  record_count: number
}

export type Health = {
  status: string
  env: string
  apps: HealthApp[]
  audit: { entries: number; chain_ok: boolean }
}

export type AuditEntry = {
  id: number
  ts: string
  app: string | null
  actor_id: string | null
  action: string
  record_type: string | null
  record_id: string | null
  request_id: string | null
  diff: Record<string, unknown>
  prev_hash: string
  hash: string
}

/** A record's history entry; roles without audit.read get these without the oversight fields. */
export type HistoryEntry = Omit<AuditEntry, "request_id" | "prev_hash" | "hash"> &
  Partial<Pick<AuditEntry, "request_id" | "prev_hash" | "hash">>

export type VerifyResult = {
  ok: boolean
  entries: number
  first_bad_id: number | null
  reason: string | null
}

export type ListQuery = Record<string, string | number | boolean | null | undefined>

export function qs(query: ListQuery): string {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null || value === "") continue
    params.set(key, String(value))
  }
  const text = params.toString()
  return text ? `?${text}` : ""
}

type RequestOptions = { method?: string; body?: unknown; silent?: boolean }

/** Every API call goes through here. Any non-2xx answer becomes an ApiError and, unless `silent`, a toast
 * showing the refusal code and message, so no control failure is ever swallowed by the UI. */
export async function api<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" }
  const persona = getPersonaId()
  if (persona) headers["X-Dev-User"] = persona
  if (options.body !== undefined) headers["Content-Type"] = "application/json"
  let response: Response
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method: options.method ?? "GET",
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
    })
  } catch {
    const error = new ApiError(0, "NETWORK_ERROR", "The API is not reachable.")
    if (!options.silent) showApiError(error)
    throw error
  }
  if (response.ok) {
    if (response.status === 204) return undefined as T
    return (await response.json()) as T
  }
  let code = `HTTP_${response.status}`
  let message = response.statusText || "Request failed."
  try {
    const body = (await response.json()) as { code?: string; message?: string; detail?: unknown }
    if (body.code) code = body.code
    if (body.message) message = body.message
    else if (typeof body.detail === "string") message = body.detail
  } catch {
    // keep defaults
  }
  const error = new ApiError(response.status, code, message)
  if (!options.silent) showApiError(error)
  throw error
}

export function showApiError(error: ApiError) {
  toast.error(error.code, { description: error.message, id: `${error.code}:${error.message}` })
}

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError
}
