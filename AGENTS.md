# AGENTS.md

Conventions for anyone changing this repo, human or Devin. Read this, `REVIEW.md` and `docs/ACCEPTANCE.md`
before planning.

## What this repo is

Internal tools for a regulated fintech, built on one shared foundation. Two apps today: the KYC Review Queue
and the Refunds Desk. Every app gets sign-in, roles, row-level access, masking, separation of duties and a
tamper-evident audit log from the foundation. An app adds its own models, policy, routes and screens.

## Layout

```
backend/platform/        foundation: auth, policy engine, masking, approvals (SoD), audit log, paging, db
backend/apps/<app>/      one folder per app: models, policy.yaml, service, routes, seed
web/src/platform/        foundation UI: design system, app shell, persona switcher, data table, audit view
web/src/apps/<app>/      one folder per app: screens built only from web/src/platform components
```

## Rules

- **Apps never edit the foundation.** Work in `backend/apps/<app>/` and `web/src/apps/<app>/`. If an app
  needs a foundation change, stop and ask. If it is approved, put it in its own commit titled
  `platform: <change>` and explain it in the PR. `scripts/foundation_diff.py` reports these lines on every PR.
- **Every control lives in the API.** UI checks are cosmetic. Every endpoint calls the policy engine, every query
  goes through the row-scope helper (lists, counts and lookups by id), and every response is serialized through
  the masking helper.
- **Every state change** goes through one service function that checks the transition, checks separation of
  duties, writes the audit entry and commits, all in one transaction.
- **Synthetic data only.** Seeded people and companies are fictional; ids start with `TEST-`. No real names,
  card numbers or ID numbers. Store only the last 4 digits of a card, never a full number.
- **No personal data in logs or audit entries.** Log ids and request ids. Masked fields are recorded in audit
  diffs as `{"changed": true}`.
- **Lists are server-side.** Paginate with the platform helper, sort only by allowlisted columns, return exact
  totals. Never return unbounded lists.
- **Sign-in is a mock.** The `X-Dev-User` header works only when `APP_ENV=dev`, and then only from loopback with
  Host `localhost` or `127.0.0.1`; otherwise every authenticated endpoint returns 401. Production would use Entra
  ID OIDC.
- **Stay in scope.** Build what the session prompt and `docs/ACCEPTANCE.md` ask for. If you think something else
  is needed, list it under "Follow-ups" in the PR instead of building it.

## Stack

- Backend: Python 3.12, FastAPI, SQLAlchemy 2, SQLite, pytest, ruff (line length 110), uv.
- Frontend: React, Vite, TypeScript (strict), Tailwind, shadcn/ui, Playwright.
- One command each: `make setup`, `make seed`, `make run`, `make web`, `make test`, `make e2e`, `make lint`.

## UI

A calm, dense internal tool in the style of Linear or Stripe's dashboard: neutral palette, one accent color,
Inter, consistent spacing, tables first. Use only components from `web/src/platform`. No charts, gradients,
illustrations or animations. Every refusal from the API is shown to the user with its code (for example
`SOD_VIOLATION`) and message.

## Pull requests

- One PR per milestone in the session prompt.
- The description lists the acceptance ids it covers (from `docs/ACCEPTANCE.md`), the checks you ran, what
  you could not finish, and follow-ups.
- CI must be green: ruff, pytest, eslint, tsc, vite build, Playwright, and the foundation diff report.
