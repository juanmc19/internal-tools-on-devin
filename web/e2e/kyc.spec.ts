import { expect, test, type Page } from "@playwright/test";

/** OVR-1 / OVR-4 / FND-4 / PRIV-1 / SCL-1 as the demo shows them. Runs against a freshly seeded API in CI and
 * against whatever is on :8000 locally; it always picks a case that is still `new`. */

const ANA = "TEST-USR-ANA";
const CAMILA = "TEST-USR-CAMILA";
const DIEGO = "TEST-USR-DIEGO";

async function switchPersona(page: Page, id: string) {
  await page.getByTestId("persona-select").click();
  await page.getByTestId(`persona-${id}`).click();
}

async function openNewCase(page: Page): Promise<string> {
  const filtered = page.waitForResponse(
    (r) =>
      r.url().includes("/kyc/cases?") &&
      new URL(r.url()).searchParams.get("status") === "new",
  );
  await page.getByTestId("filter-status").click();
  await page.getByRole("option", { name: "New", exact: true }).click();
  await filtered;
  const row = page.locator("[data-testid^='kyc-row-']").first();
  await expect(row).toContainText("New");
  const reference = (await row.getAttribute("data-testid"))!.replace(
    "kyc-row-",
    "",
  );
  await row.click();
  await expect(page.getByTestId("record-sheet")).toContainText(reference);
  return reference;
}

async function confirmDialog(
  page: Page,
  outcome: "Approve" | "Reject",
  note?: string,
) {
  const dialog = page
    .getByRole("dialog")
    .filter({ has: page.getByTestId("confirm-action") });
  await dialog.getByTestId("outcome-select").click();
  await page.getByRole("option", { name: outcome }).click();
  if (note !== undefined) await dialog.getByTestId("recommend-note").fill(note);
  await dialog.getByTestId("confirm-action").click();
}

test("analyst sees masked data, own countries only and the exact total (PRIV-1, PRIV-2, SCL-1)", async ({
  page,
}) => {
  await page.goto("/");
  await switchPersona(page, ANA);
  await expect(page.getByTestId("persona-select")).toContainText(
    "Ana Ruiz · Analyst · MX, CO",
  );
  await page
    .getByTestId("app-switcher")
    .getByRole("link", { name: "KYC" })
    .click();
  await expect(page.getByTestId("table-range")).toContainText(
    /1–50 of 1[\d,]+/,
  );
  const firstRow = page.locator("[data-testid^='kyc-row-']").first();
  await expect(firstRow).toBeVisible();
  const applicant = await firstRow.locator("td").nth(1).innerText();
  expect(applicant).toMatch(/^([A-ZÁÉÍÓÚÑ]\.\s?)+$/);
  await page.getByTestId("filter-country").click();
  const options = await page.getByRole("option").allInnerTexts();
  expect(options.join(" ")).toContain("MX");
  expect(options.join(" ")).toContain("CO");
  expect(options.join(" ")).not.toContain("BR");
  await page.keyboard.press("Escape");
  await firstRow.click();
  await expect(page.getByTestId("masking-badge")).toContainText(
    "Masked for your role",
  );
  await expect(page.getByTestId("field-applicant")).toHaveText(
    /^([A-ZÁÉÍÓÚÑ]\.\s?)+$/,
  );
  await expect(page.getByTestId("kyc-tabs")).not.toContainText("Audit log");
});

test("recommender is refused on Decide, another senior reviewer decides, chain verifies (OVR-1, OVR-4)", async ({
  page,
}) => {
  await page.goto("/kyc");
  await switchPersona(page, CAMILA);
  await expect(page.getByTestId("persona-select")).toContainText(
    "Camila Torres · Senior reviewer · All",
  );
  const reference = await openNewCase(page);
  await expect(page.getByTestId("masking-badge")).toContainText("Unmasked");

  await page.getByTestId("action-claim").click();
  await expect(page.getByTestId("record-sheet")).toContainText("In review");
  await page.getByTestId("action-recommend").click();
  await confirmDialog(
    page,
    "Approve",
    "Documents consistent; screening clear.",
  );
  await expect(page.getByTestId("record-sheet")).toContainText("Recommended");
  await expect(page.getByTestId("history-timeline")).toContainText(
    "Recommended",
  );
  await expect(page.getByTestId("history-timeline")).toContainText(
    "Assigned to Camila Torres",
  );
  await expect(page.getByTestId("history-timeline")).toContainText(
    "Viewed unmasked: name, date of birth, ID number, address",
  );

  // same person tries to decide: the button is there, the API refuses
  await page.getByTestId("action-decide").click();
  await confirmDialog(page, "Approve");
  const toast = page
    .locator("[data-sonner-toast]")
    .filter({ hasText: "SOD_VIOLATION" });
  await expect(toast).toBeVisible();
  await expect(toast).toContainText("Separation of duties");
  await expect(page.getByTestId("record-sheet")).toContainText("Recommended");
  await expect(page.getByTestId("history-timeline")).toContainText(
    "SOD_VIOLATION",
  );

  // a different senior reviewer decides: close the sheet, switch persona, reopen the case
  await page
    .getByTestId("record-sheet")
    .getByRole("button", { name: "Close" })
    .click();
  await expect(page.getByTestId("record-sheet")).toBeHidden();
  await switchPersona(page, DIEGO);
  await page.getByTestId("filter-status").click();
  await page.getByRole("option", { name: "Recommended", exact: true }).click();
  await page.getByTestId("kyc-search").fill(reference);
  await page.getByTestId(`kyc-row-${reference}`).click();
  await expect(page.getByTestId("record-sheet")).toContainText(reference);
  await page.getByTestId("action-decide").click();
  await confirmDialog(page, "Approve");
  await expect(page.getByTestId("record-sheet")).toContainText("Approved");
  await expect(page.getByTestId("history-timeline")).toContainText("Decided");

  // audit view: entries for the case and a verified chain
  await page
    .getByTestId("record-sheet")
    .getByRole("button", { name: "Close" })
    .click();
  await expect(page.getByTestId("record-sheet")).toBeHidden();
  await page
    .getByTestId("kyc-tabs")
    .getByRole("link", { name: "Audit log" })
    .click();
  await page.getByPlaceholder("Filter by record reference").fill(reference);
  await expect(page.getByTestId("table-range")).toContainText(
    /of [5-9]|of \d{2,}/,
  );
  await expect(page.locator("table")).toContainText("SOD_VIOLATION");
  await page.getByTestId("verify-chain").click();
  await expect(page.getByTestId("verify-result")).toContainText(
    /intact|ok|verified/i,
  );
});
