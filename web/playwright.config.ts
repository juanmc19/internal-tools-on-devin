import path from "node:path"
import { fileURLToPath } from "node:url"
import { defineConfig, devices } from "@playwright/test"

const here = path.dirname(fileURLToPath(import.meta.url))

const isCI = !!process.env.CI
const repoRoot = path.resolve(here, "..")
const e2eDb = path.join(here, "test-results", "e2e.db")
const backendEnv = `APP_ENV=dev DATABASE_URL=sqlite:///${e2eDb}`

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  retries: isCI ? 1 : 0,
  reporter: isCI ? [["list"], ["html", { open: "never" }]] : "list",
  timeout: 45_000,
  use: {
    baseURL: "http://127.0.0.1:5173",
    viewport: { width: 1440, height: 900 },
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: `mkdir -p test-results && cd ${repoRoot} && ${backendEnv} uv run --project backend --no-sync python -m backend.seed && ${backendEnv} uv run --project backend --no-sync uvicorn backend.main:app --host 127.0.0.1 --port 8000`,
      url: "http://127.0.0.1:8000/health",
      reuseExistingServer: !isCI,
      timeout: 180_000,
    },
    {
      command: "npm run dev",
      url: "http://127.0.0.1:5173",
      reuseExistingServer: !isCI,
      timeout: 60_000,
    },
  ],
})
