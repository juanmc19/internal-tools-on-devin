import { expect, test, type Page } from "@playwright/test"

/** FND-4: the shell has a persona switcher marked DEV ONLY, an app switcher, and shows API refusals with
 * their code. The refusal here is injected at the network layer because PR 1 ships no app yet; the KYC
 * e2e proves the same toast on a real SOD_VIOLATION. */

const PERSONAS = {
  items: [
    {
      id: "TEST-USR-E2E-1",
      name: "Ana Ruiz",
      roles: [
        {
          app: "demo",
          app_name: "Demo",
          role: "analyst",
          role_label: "Analyst",
          permissions: ["demo.read"],
          masked: true,
          scope: ["MX", "CO"],
        },
      ],
    },
  ],
}

async function mockPersonas(page: Page) {
  await page.route("**/api/dev/users", (route) => route.fulfill({ json: PERSONAS }))
}

test("FND-4 shell: app switcher, DEV ONLY persona switcher with name · role · scope", async ({ page }) => {
  await mockPersonas(page)
  await page.goto("/")
  const nav = page.getByTestId("app-switcher")
  await expect(nav.getByRole("link", { name: "Home" })).toBeVisible()
  await expect(page.getByTestId("dev-only-badge")).toHaveText("DEV ONLY")
  await page.getByTestId("persona-select").click()
  await page.getByTestId("persona-TEST-USR-E2E-1").click()
  await expect(page.getByTestId("persona-select")).toContainText("Ana Ruiz · Analyst · MX, CO")
  await expect(page.getByRole("heading", { name: "Home" })).toBeVisible()
})

test("FND-4 refusals: an API 403 is shown as a toast with its code and message", async ({ page }) => {
  await mockPersonas(page)
  await page.route("**/api/health", (route) =>
    route.fulfill({
      status: 403,
      json: { code: "SOD_VIOLATION", message: "Separation of duties: the recommender cannot decide this case." },
    }),
  )
  await page.goto("/")
  const toast = page.locator("[data-sonner-toast]").first()
  await expect(toast).toContainText("SOD_VIOLATION")
  await expect(toast).toContainText("Separation of duties: the recommender cannot decide this case.")
})

test("Home lists apps from /health with live counts and audit chain status", async ({ page }) => {
  await mockPersonas(page)
  await page.route("**/api/health", (route) =>
    route.fulfill({
      json: {
        status: "ok",
        env: "dev",
        apps: [
          {
            key: "demo",
            name: "Demo",
            owner_team: "Platform",
            description: "A demo app.",
            web_path: "/demo",
            status: "ok",
            record_count: 50000,
          },
        ],
        audit: { entries: 12, chain_ok: true },
      },
    }),
  )
  await page.goto("/")
  const card = page.getByTestId("app-card-demo")
  await expect(card).toContainText("Demo")
  await expect(card).toContainText("Platform")
  await expect(card).toContainText("50,000")
  await expect(card).toContainText("Intact")
  await expect(card).toContainText("Healthy")
})
