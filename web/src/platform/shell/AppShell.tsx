import { NavLink, Outlet } from "react-router-dom"
import { cn } from "@/platform/lib/utils"
import { PersonaSwitcher } from "@/platform/shell/PersonaSwitcher"
import { APPS } from "@/apps/registry"

const linkClass = ({ isActive }: { isActive: boolean }) =>
  cn(
    "rounded-md px-2.5 py-1 text-sm font-medium transition-colors",
    isActive ? "bg-muted text-foreground" : "text-muted-foreground hover:bg-muted/60 hover:text-foreground",
  )

export function AppShell() {
  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-20 border-b bg-background/95 backdrop-blur">
        <div className="mx-auto flex h-12 max-w-[1400px] items-center gap-4 px-4">
          <div className="flex items-center gap-1.5 pr-2">
            <span className="inline-block size-4 rounded-sm bg-primary" aria-hidden />
            <span className="text-sm font-semibold tracking-tight">Internal tools</span>
          </div>
          <nav className="flex items-center gap-1" aria-label="Apps" data-testid="app-switcher">
            <NavLink to="/" end className={linkClass}>
              Home
            </NavLink>
            {APPS.map((app) => (
              <NavLink key={app.key} to={app.path} className={linkClass}>
                {app.name}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto">
            <PersonaSwitcher />
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-[1400px] px-4 py-5">
        <Outlet />
      </main>
    </div>
  )
}
