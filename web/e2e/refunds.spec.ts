import { expect, test, type Page } from "@playwright/test";

/** REP-1 to REP-4 as the demo shows them: a $7,500 refund needs two different approvers, the same approver
 * is refused a second time, finance pays, the chain verifies; and an approver who requested a refund is
 * refused with SOD_VIOLATION when approving it. TLR-2: the queue sorted by Reg E deadline puts overdue
 * disputes first, flagged in red. Runs against a seeded API; it creates its own refunds. */

const GABRIELA = "TEST-USR-GABRIELA";
const INES = "TEST-USR-INES";
const JAVIER = "TEST-USR-JAVIER";
const KARLA = "TEST-USR-KARLA";
const ELENA = "TEST-USR-ELENA";

async function switchPersona(page: Page, id: string) {
  await page.getByTestId("persona-select").click();
  await page.getByTestId(`persona-${id}`).click();
}

/** Fills the New refund form and returns the reference the API assigned. The sheet opens on the new refund. */
async function requestRefund(
  page: Page,
  { customer, amount }: { customer: string; amount: string },
): Promise<string> {
  await page.getByTestId("new-refund").click();
  const dialog = page
    .getByRole("dialog")
    .filter({ has: page.getByTestId("new-submit") });
  await dialog.getByTestId("new-customer").fill(customer);
  await dialog.getByTestId("new-last4").fill("4242");
  await dialog.getByTestId("new-amount").fill(amount);
  await dialog
    .getByTestId("new-reason")
    .fill("Duplicate charge on the statement.");
  const created = page.waitForResponse(
    (r) => r.url().endsWith("/refunds") && r.request().method() === "POST",
  );
  await dialog.getByTestId("new-submit").click();
  const body = (await (await created).json()) as { reference: string };
  await expect(page.getByTestId("record-sheet")).toContainText(body.reference);
  return body.reference;
}

async function closeSheet(page: Page) {
  await page
    .getByTestId("record-sheet")
    .getByRole("button", { name: "Close" })
    .click();
  await expect(page.getByTestId("record-sheet")).toBeHidden();
}

async function openRefund(page: Page, reference: string, status?: string) {
  if (status) {
    await page.getByTestId("filter-status").click();
    await page.getByRole("option", { name: status, exact: true }).click();
  }
  await page.getByTestId("refunds-search").fill(reference);
  await page.getByTestId(`refunds-row-${reference}`).click();
  await expect(page.getByTestId("record-sheet")).toContainText(reference);
}

async function expectSodRefusal(page: Page) {
  const toast = page
    .locator("[data-sonner-toast]")
    .filter({ hasText: "SOD_VIOLATION" });
  await expect(toast).toBeVisible();
  await expect(toast).toContainText("Separation of duties");
  await expect(page.getByTestId("history-timeline")).toContainText(
    "SOD_VIOLATION",
  );
}

test("$7,500 refund: two approvers, same approver refused twice, finance pays, chain verifies (REP-1, REP-3, REP-4)", async ({
  page,
}) => {
  await page.goto("/refunds");
  await switchPersona(page, GABRIELA);
  await expect(page.getByTestId("persona-select")).toContainText(
    "Gabriela Soto · Agent",
  );
  await expect(page.getByTestId("table-range")).toContainText(/1–50 of [\d,]+/);

  // agent requests: only the last 4 digits are entered, the agent sees the customer as initials
  const reference = await requestRefund(page, {
    customer: "Test Customer",
    amount: "7500",
  });
  const sheet = page.getByTestId("record-sheet");
  await expect(sheet).toContainText("Requested");
  await expect(page.getByTestId("field-amount")).toHaveText("$7,500.00");
  await expect(page.getByTestId("field-approvals-required")).toContainText("2");
  await expect(page.getByTestId("field-card")).toContainText("•••• 4242");
  await expect(page.getByTestId("masking-badge")).toContainText(
    "Masked for your role",
  );
  await expect(page.getByTestId("field-customer")).toHaveText("T. C.");
  await expect(page.getByTestId("action-approve")).toHaveCount(0);
  await closeSheet(page);

  // first approver: stays pending second approval; a second click by the same person is refused
  await switchPersona(page, INES);
  await openRefund(page, reference);
  await expect(page.getByTestId("masking-badge")).toContainText("Unmasked");
  await expect(page.getByTestId("field-customer")).toHaveText("Test Customer");
  await page.getByTestId("action-approve").click();
  await expect(sheet).toContainText("Pending second approval");
  await expect(page.getByTestId("approvals-timeline")).toContainText(
    "1 of 2 · Inés Castillo",
  );
  await expect(page.getByTestId("approvals-timeline")).toContainText(
    "awaiting a different approver",
  );
  await page.getByTestId("action-approve").click();
  await expectSodRefusal(page);
  await expect(sheet).toContainText("Pending second approval");
  await closeSheet(page);

  // second approver completes the rule
  await switchPersona(page, JAVIER);
  await openRefund(page, reference);
  await page.getByTestId("action-approve").click();
  await expect(sheet).toContainText("Approved");
  await expect(page.getByTestId("approvals-timeline")).toContainText(
    "2 of 2 · Javier Ortiz",
  );
  await expect(page.getByTestId("history-timeline")).toContainText(
    "Approvals: 2 of 2",
  );
  await closeSheet(page);

  // finance pays
  await switchPersona(page, KARLA);
  await openRefund(page, reference, "Approved");
  await expect(page.getByTestId("action-approve")).toHaveCount(0);
  await page.getByTestId("action-pay").click();
  await expect(sheet).toContainText("Paid");
  await expect(page.getByTestId("history-timeline")).toContainText(
    "Marked paid",
  );
  await closeSheet(page);

  // auditor (Elena also audits KYC) sees the trail and verifies the chain
  await switchPersona(page, ELENA);
  await page
    .getByTestId("refunds-tabs")
    .getByRole("link", { name: "Audit log" })
    .click();
  await page.getByPlaceholder("Filter by record reference").fill(reference);
  await expect(page.getByTestId("table-range")).toContainText(
    /of [5-9]|of \d{2,}/,
  );
  await expect(page.locator("table")).toContainText("SOD_VIOLATION");
  await expect(page.locator("table")).toContainText("Marked paid");
  await page.getByTestId("verify-chain").click();
  await expect(page.getByTestId("verify-result")).toContainText(
    /intact|ok|verified/i,
  );
});

test("approver who requested a refund is refused with SOD_VIOLATION on Approve (REP-2)", async ({
  page,
}) => {
  await page.goto("/refunds");
  await switchPersona(page, INES);
  await expect(page.getByTestId("persona-select")).toContainText(
    "Inés Castillo · Approver",
  );
  const reference = await requestRefund(page, {
    customer: "Self Service",
    amount: "120",
  });
  const sheet = page.getByTestId("record-sheet");
  await expect(sheet).toContainText("Requested");
  await expect(page.getByTestId("sod-hint")).toContainText(
    "You requested this refund",
  );

  // the button is there, the API refuses
  await page.getByTestId("action-approve").click();
  await expectSodRefusal(page);
  await expect(sheet).toContainText("Requested");
  await expect(page.getByTestId("approvals-timeline")).not.toContainText(
    "1 of 1 · Inés",
  );
  await closeSheet(page);

  // a different approver can
  await switchPersona(page, JAVIER);
  await openRefund(page, reference);
  await page.getByTestId("action-approve").click();
  await expect(sheet).toContainText("Approved");
  await expect(page.getByTestId("approvals-timeline")).toContainText(
    "1 of 1 · Javier Ortiz",
  );
});

test("queue sorted by Reg E deadline shows overdue disputes first, flagged; goodwill has none (TLR-2, TLR-3)", async ({
  page,
}) => {
  await page.goto("/refunds");
  await switchPersona(page, INES);
  await expect(page.getByTestId("table-range")).toContainText(/1–50 of [\d,]+/);

  // most urgent first: the open queue sorted by deadline starts with overdue disputes in red
  const sorted = page.waitForResponse(
    (r) =>
      r.url().includes("/refunds?") && r.url().includes("sort=deadline_on"),
  );
  await page.getByRole("columnheader", { name: "Reg E deadline" }).click();
  await sorted;
  const header = page.getByRole("columnheader", { name: "Reg E deadline" });
  await expect(header).toHaveAttribute("aria-sort", "ascending");
  const rows = page.locator("tbody tr");
  await expect(rows.first().getByTestId("deadline-overdue")).toContainText(
    /Overdue · \d+ business days?/,
  );
  await expect(
    rows.first().locator("[data-testid=deadline-overdue] span"),
  ).toHaveClass(/text-red-700/);
  await expect(page.getByTestId("deadline-overdue").first()).toBeVisible();

  // the sheet shows the deadline date next to the flag
  await rows.first().click();
  await expect(page.getByTestId("field-deadline")).toContainText("Overdue");
  await expect(page.getByTestId("field-deadline")).toContainText(
    /\d{2} \w{3} \d{4}/,
  );
  await closeSheet(page);

  // goodwill refunds have no deadline and sort after every dispute
  const goodwill = page.waitForResponse(
    (r) => r.url().includes("/refunds?") && r.url().includes("type=goodwill"),
  );
  await page.getByTestId("filter-type").click();
  await page.getByRole("option", { name: "Goodwill", exact: true }).click();
  await goodwill;
  await expect(rows.first().getByTestId("deadline-none")).toHaveText("—");
  await expect(page.getByTestId("deadline-overdue")).toHaveCount(0);
});

test("a dispute reported more than 2 years ago is refused with REPORTED_ON_TOO_OLD", async ({
  page,
}) => {
  await page.goto("/refunds");
  await switchPersona(page, GABRIELA);
  await page.getByTestId("new-refund").click();
  const dialog = page
    .getByRole("dialog")
    .filter({ has: page.getByTestId("new-submit") });
  await dialog.getByTestId("new-customer").fill("Test Customer");
  await dialog.getByTestId("new-last4").fill("4242");
  await dialog.getByTestId("new-amount").fill("25");
  await dialog.getByTestId("new-type").click();
  await page.getByRole("option", { name: "Dispute", exact: true }).click();
  await dialog.getByTestId("new-reported").fill("2001-01-01");
  await dialog
    .getByTestId("new-reason")
    .fill("Customer does not recognise the transaction.");
  await dialog.getByTestId("new-submit").click();
  const toast = page
    .locator("[data-sonner-toast]")
    .filter({ hasText: "REPORTED_ON_TOO_OLD" });
  await expect(toast).toBeVisible();
  await expect(toast).toContainText(
    "The report date cannot be more than 2 years ago.",
  );
  await expect(dialog).toBeVisible();
});
