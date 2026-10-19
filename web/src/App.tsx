import { BrowserRouter, Route, Routes } from "react-router-dom"
import { TooltipProvider } from "@/platform/ui/tooltip"
import { Toaster } from "@/platform/ui/sonner"
import { PersonaProvider } from "@/platform/persona"
import { AppShell } from "@/platform/shell/AppShell"
import { Home } from "@/platform/pages/Home"
import { APPS } from "@/apps/registry"

export default function App() {
  return (
    <BrowserRouter>
      <TooltipProvider>
        <PersonaProvider>
          <Routes>
            <Route element={<AppShell />}>
              <Route index element={<Home />} />
              {APPS.map((app) => (
                <Route key={app.key} path={`${app.path}/*`} element={<app.component />} />
              ))}
            </Route>
          </Routes>
          <Toaster position="bottom-right" richColors closeButton theme="light" />
        </PersonaProvider>
      </TooltipProvider>
    </BrowserRouter>
  )
}
