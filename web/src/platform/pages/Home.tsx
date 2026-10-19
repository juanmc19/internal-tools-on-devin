import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { ArrowRight, ShieldCheck, ShieldX } from "lucide-react"
import { api, type Health } from "@/platform/api"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/platform/ui/card"
import { Skeleton } from "@/platform/ui/skeleton"
import { Button } from "@/platform/ui/button"
import { StatusBadge } from "@/platform/components/StatusBadge"
import { EmptyState } from "@/platform/components/EmptyState"
import { PageHeader } from "@/platform/shell/PageHeader"
import { formatInt } from "@/platform/format"
import { APPS } from "@/apps/registry"

export function Home() {
  const [health, setHealth] = useState<Health | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    api<Health>("/health")
      .then(setHealth)
      .catch(() => setFailed(true))
  }, [])

  return (
    <>
      <PageHeader
        title="Home"
        description="Every app below runs on the shared foundation: sign-in, roles, row-level access, masking, separation of duties and a tamper-evident audit log."
      />
      {failed ? (
        <EmptyState title="The API is not reachable" description="Start it with `make run` and reload." />
      ) : !health ? (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 2 }).map((_, i) => (
            <Skeleton key={i} className="h-44" />
          ))}
        </div>
      ) : health.apps.length === 0 ? (
        <EmptyState title="No apps registered yet" description="Apps register in backend/apps and web/src/apps." />
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3" data-testid="home-cards">
          {health.apps.map((app) => {
            const def = APPS.find((a) => a.key === app.key)
            return (
              <Card key={app.key} className="gap-4" data-testid={`app-card-${app.key}`}>
                <CardHeader>
                  <div className="flex items-center justify-between gap-2">
                    <CardTitle>{app.name}</CardTitle>
                    <StatusBadge value={app.status} tone={app.status === "ok" ? "success" : "danger"} label={app.status === "ok" ? "Healthy" : "Degraded"} />
                  </div>
                  <CardDescription>{app.description}</CardDescription>
                </CardHeader>
                <CardContent>
                  <dl className="grid grid-cols-3 gap-3 text-sm">
                    <div>
                      <dt className="text-xs text-muted-foreground">Owner</dt>
                      <dd>{app.owner_team}</dd>
                    </div>
                    <div>
                      <dt className="text-xs text-muted-foreground">Records</dt>
                      <dd className="tabular-nums">{formatInt(app.record_count)}</dd>
                    </div>
                    <div>
                      <dt className="text-xs text-muted-foreground">Audit chain</dt>
                      <dd className={health.audit.chain_ok ? "inline-flex items-center gap-1 text-emerald-700" : "inline-flex items-center gap-1 text-red-700"}>
                        {health.audit.chain_ok ? <ShieldCheck className="size-3.5" /> : <ShieldX className="size-3.5" />}
                        {health.audit.chain_ok ? "Intact" : "Broken"}
                      </dd>
                    </div>
                  </dl>
                </CardContent>
                <CardFooter className="mt-auto">
                  {def ? (
                    <Button asChild variant="outline" size="sm">
                      <Link to={def.path}>
                        Open {app.name} <ArrowRight />
                      </Link>
                    </Button>
                  ) : (
                    <span className="text-xs text-muted-foreground">No web app registered for {app.key}.</span>
                  )}
                </CardFooter>
              </Card>
            )
          })}
        </div>
      )}
    </>
  )
}
