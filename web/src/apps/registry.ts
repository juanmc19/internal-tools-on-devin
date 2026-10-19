import type { ComponentType } from "react"

/** Apps register here (outside the foundation) so the shell, routes and Home stay app-agnostic. */
export type AppDefinition = {
  key: string
  name: string
  path: string
  /** Rendered under `path/*`; the app owns its nested routes. */
  component: ComponentType
}

export const APPS: AppDefinition[] = []
