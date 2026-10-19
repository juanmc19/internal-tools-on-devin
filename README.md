# internal-tools-on-devin

A prototype for a build-vs-buy question: can a Series C fintech with about 60 engineers build its internal
tools with Devin instead of Microsoft Power Apps? It contains two apps on one shared foundation, both built by
Devin in recorded sessions:

- **KYC Review Queue:** analysts claim and recommend cases, senior reviewers decide.
- **Refunds Desk:** agents request refunds, approvers approve them, two approvers above $5,000.

Both apps get sign-in, roles, row-level access, masking, separation of duties and a tamper-evident audit log from
the foundation. What each claim rests on is in [docs/ACCEPTANCE.md](docs/ACCEPTANCE.md); what each session
cost is in [docs/RECEIPTS.md](docs/RECEIPTS.md).

## Run it

Needs Python 3.12 (via [uv](https://docs.astral.sh/uv/)) and Node 20.

```sh
make setup   # uv sync, npm ci, Playwright Chromium
make seed    # recreate backend/data/app.db and seed every registered app
make run     # API on http://127.0.0.1:8000 (APP_ENV=dev turns on the mock sign-in)
make web     # web on http://127.0.0.1:5173 (proxies /api to :8000)
```

Then `make test` (pytest), `make lint` (ruff, eslint, tsc), `make e2e` (Playwright; starts both servers against
a fresh seeded database), `make bench` (p95 for list, filter, search) and `make foundation-diff` (lines changed
under `backend/platform/` and `web/src/platform/` against `main`).

Sign-in is mocked: pick a persona in the top bar (marked DEV ONLY). The `X-Dev-User` header it sends is only
honoured when `APP_ENV=dev`; every authenticated endpoint returns 401 otherwise. Personas are seeded by each app.

Layout and conventions are in [AGENTS.md](AGENTS.md); the review checklist is [REVIEW.md](REVIEW.md).

## Real vs mocked

| Real | Mocked |
|---|---|
| Roles, row-level access, masking, separation of duties, audit log and their tests | Sign-in: a DEV ONLY persona switcher instead of Entra ID |
| Server-side paging over 50,000 synthetic cases | All data is synthetic |
| CI checks, including the foundation diff report | SQLite instead of Postgres |

## Assumptions

The brief leaves these open. They shape the recommendation and should be checked with the client.

1. **Engineers build the apps; the rest of the company uses them.** The brief says the VP of Engineering is
   asking whether "the team" can build them with Devin.
2. **Microsoft shop.** The company already uses Entra ID and Microsoft 365, so Power Apps sign-in and
   connectors come at no extra effort.
3. **Regulated.** KYC/AML obligations apply, directly or through a sponsor bank, and SOX controls are coming
   ahead of an IPO.
4. **The $250K covers more than seats.** At $20 per user per month, $250K is about 1,040 Premium seats, more than
   a company with ~60 engineers likely employs. The bill probably includes Dataverse capacity, Power Automate or
   other Microsoft products. The first thing to ask for is the invoice by SKU and the renewal date.
5. **License savings come only when whole user groups leave.** Premium is billed per user, so a seat goes away
   only when its user no longer needs any Power App.
6. **The 10 planned apps are not named in the brief.** The recommendation routes each one through the same
   three gates (build, buy, keep) instead of guessing what they are.
7. **Loaded engineer cost of about $200K a year**, used only to reason about review time.
8. **Prototype limits.** Synthetic data, mocked sign-in, SQLite, no deployment pipeline.

## Sources

- Delegation limits in canvas apps (500 rows by default, 10,000 at most):
  [Microsoft Learn](https://learn.microsoft.com/en-us/power-apps/maker/canvas-apps/delegation-overview)
- Dataverse auditing is turned on per environment, table and column, does not log reads, and admins can delete
  logs: [Microsoft Learn](https://learn.microsoft.com/en-us/power-platform/admin/manage-dataverse-auditing)
- Power Apps Premium rises from $20 to $22 per user per month on January 1, 2027:
  [Microsoft licensing news, Sep 9, 2026](https://www.microsoft.com/en-us/licensing/news/power-apps-premium-price-update)
- Power Apps Test Engine is deprecated in favor of Playwright samples:
  [Microsoft Learn](https://learn.microsoft.com/en-sg/power-platform/test-engine),
  [migration guide](https://learn.microsoft.com/power-platform/developer/playwright-samples/migration-guide)
- 1,000+ Power Platform connectors:
  [Microsoft Learn training](https://learn.microsoft.com/en-us/training/modules/identify-foundational-components-microsoft-power-platfor/5-examine-power-platform-connectors)
- Reg E error resolution (10 business days to investigate):
  [12 CFR 1005.11](https://www.consumerfinance.gov/rules-policy/regulations/1005/11/)

## How it was built

`AGENTS.md` and `REVIEW.md` are the conventions Devin followed. The prompt for each session is in
[docs/devin-sessions](docs/devin-sessions). Every change went through a PR with CI, Devin Review and my review.
