# Internal tools on Devin

A working prototype of two internal tools for a regulated fintech, built by Devin on one shared foundation: a
**KYC Review Queue** and a **Refunds Desk**. Every control (who can see what, who can approve what, and what gets
recorded) is enforced by the API from a single policy file per app, so a new app inherits all of it without writing
new security code.

## What it does

### Home

Lists every app on the foundation with its owning team, record count and audit chain status. A persona menu in
the top bar (marked DEV ONLY) switches between demo users and stands in for real sign-in; it only works on
`localhost`.

### KYC Review Queue

Customer onboarding cases (50,000 across six Latin American countries) move from **New → In review → Recommended →
Approved or Rejected**.

| Role | Can do |
|---|---|
| Analyst | Claim and recommend cases in their assigned countries |
| Senior reviewer | Claim, recommend and decide any case; sees full applicant details |
| Auditor | Read cases and the audit log |

| Policy | How it works |
|---|---|
| Row-level access | Analysts only receive cases from their countries. Other cases return "not found" and are left out of counts. |
| Masking | Analysts and auditors see initials, the last 4 digits of the ID, the city (the street address is hidden) and the day of birth. Every unmasked read by a senior reviewer is logged. |
| Four-eyes rule | Whoever recommends a case cannot decide it. The API refuses with `SOD_VIOLATION`, and the attempt is logged. |
| Server-side paging | Filters, search and totals run on the server across every case, so nothing is silently cut off. |
| Audit log | Claims, recommendations, decisions, unmasked reads and refusals are recorded. Senior reviewers and auditors see the full log; analysts see only the workflow steps on a case. |

### Refunds Desk

Card refunds (20,000 across four US regions, either goodwill or a customer dispute) move from **Requested →
Approved → Paid**, passing through **Pending second approval** when they're above $5,000, or are rejected.

| Role | Can do |
|---|---|
| Agent | Request refunds in their regions |
| Approver | Request, approve or reject any refund |
| Finance | Mark approved refunds as paid |
| Auditor | Read refunds and the audit log |

| Policy | How it works |
|---|---|
| Two approvers above $5,000 | A large refund stays pending after the first approval and needs a second, different approver. |
| Separation of duties | A requester can't approve their own refund, and an approver can't approve the same refund twice (`SOD_VIOLATION`). |
| Row-level access | Agents only see and request refunds in their regions. |
| Masking and card data | Agents and auditors see customer names as initials. Only the last 4 digits of a card are stored; a full card number is rejected. |
| Reg E deadline | Disputes show the business days left in the 10-business-day Reg E investigation window (weekends and US federal holidays excluded). The queue sorts by urgency; overdue or due today shows in red, the next 2 days in amber. Goodwill refunds have no deadline. |
| Audit log | Requests, approvals, rejections, payments and refusals are recorded. Approvers and auditors see the full log; agents and finance see only the workflow steps on a refund. |

### Shared foundation

- Sign-in, roles, row-level access, masking, separation of duties and the audit log live once in
  `backend/platform/` and `web/src/platform/`. Apps don't edit it; foundation changes go in their own `platform:`
  commits.
- Each app declares its rules in `backend/apps/<app>/policy.yaml`, and the foundation enforces them. A policy that
  names a field the app doesn't have stops the API from starting instead of silently skipping the rule.
- The audit log is hash-chained, and database triggers block edits and deletes. **Verify chain** re-checks the
  whole log and reports the first altered entry.
- The Refunds Desk and the later Reg E change were both built without changing a line of the foundation; CI
  reports foundation lines changed on every pull request.

## Repository layout

```
backend/platform/     shared API foundation: sign-in, policy engine, masking, paging, audit log
backend/apps/<app>/   one folder per app: models, routes, service, policy.yaml, seed
backend/tests/        foundation tests, plus one folder per app
web/src/platform/     shared UI: app shell, data table, record sheet, history timeline
web/src/apps/<app>/   one folder per app's screens, registered in web/src/apps/registry.ts
web/e2e/              Playwright browser tests
scripts/              foundation_diff.py, the CI check on foundation changes
docs/                 acceptance criteria, Devin session prompts, receipts
```

## Assumptions

- **Regulated fintech.** KYC and Reg E obligations apply, which is why masking, the four-eyes rule, two-approver
  refunds and a tamper-evident log are built in from the start.
- **Microsoft shop.** In production, sign-in would use the existing Entra ID; here it's a mock persona menu.
- **Synthetic data only.** All records are generated, and SQLite stands in for a production database.
- **Business details are illustrative:** six onboarding countries, four refund regions and the $5,000
  two-approver threshold.
- **Reg E scope.** The prototype tracks only the 10-business-day Reg E investigation window from the customer's
  report; it does not model the provisional-credit extension to 45 or 90 days or the customer's 60-day reporting
  window.

## Run it

Needs Python 3.12 (via [uv](https://docs.astral.sh/uv/)) and Node 20.

```sh
make setup   # install dependencies and the Playwright browser
make seed    # reset the database and load the synthetic data
make run     # API on http://127.0.0.1:8000
make web     # web app on http://127.0.0.1:5173
```

Open http://127.0.0.1:5173 and pick a persona from the top-right menu:

| Persona | App | Role |
|---|---|---|
| Ana Ruiz | KYC | Analyst (Mexico, Colombia) |
| Bruno Lima | KYC | Analyst (Brazil, Argentina) |
| Camila Torres, Diego Marín | KYC | Senior reviewers |
| Gabriela Soto | Refunds | Agent (Northeast, Southeast) |
| Hugo Pérez | Refunds | Agent (Midwest, West) |
| Inés Castillo, Javier Ortiz | Refunds | Approvers |
| Karla Núñez | Refunds | Finance |
| Elena Vega | Both | Auditor |

`make seed` can run while the API is up. `make help` lists every target, including `make test` (backend tests),
`make e2e` (browser tests), `make lint`, `make bench` (query timings) and `make foundation-diff` (foundation lines
changed against `main`).

## How it was built

Built by Devin in three sessions, one prompt each: the foundation and KYC, then Refunds, then the Reg E change as
an ops lead would request it. Devin's security scan then reviewed the whole repo, and Devin fixed what it found in
parallel sessions, with Devin Review checking each fix. The prompts are in [docs/devin-sessions](docs/devin-sessions),
and Devin followed [AGENTS.md](AGENTS.md) and [REVIEW.md](REVIEW.md). Every change went through a pull request with
CI. [docs/ACCEPTANCE.md](docs/ACCEPTANCE.md) maps each policy above to the test that proves it, and
[docs/RECEIPTS.md](docs/RECEIPTS.md) records each session's cost and review findings.
