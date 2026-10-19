# Session 1: foundation and KYC Review Queue

Read `AGENTS.md`, `REVIEW.md` and `docs/ACCEPTANCE.md` first. They are part of this prompt.

## Context

A Series C fintech (about 60 engineers) runs its internal tools on Microsoft Power Apps and plans 10 more. We
are testing whether its engineers can build these tools with you instead. The test is two apps on one shared
foundation: this session builds the foundation and the first app, the KYC Review Queue. A later session builds a
Refunds Desk on the same foundation without changing it, so design the foundation as the paved road every app
inherits, configured per app through `policy.yaml`.

Everything is synthetic. Quality matters most in the controls: they must hold on every path and be proven by
tests. The UI should look like a well-made internal tool, built from one small design system.

## Process

1. Before writing code, post a plan: milestones, main files, risks, and your estimated cost for each PR. Wait
   for my approval.
2. Build PR 1 (foundation). Open it, then continue with PR 2 on a branch stacked on PR 1 while I review.
   Address review comments on both.
3. If you expect to go more than 25% over your estimate, stop and tell me why before continuing.
4. In each PR description, list the acceptance ids covered, the checks you ran, anything not finished and
   follow-ups.

## PR 1: Foundation

Backend (`backend/platform/`):
- **Mock sign-in:** `X-Dev-User` header, accepted only when `APP_ENV=dev`; 401 otherwise. `GET /me` and
  `GET /dev/users` for the persona switcher.
- **Policy engine:** loads each app's `policy.yaml` (roles, permissions, row scope, masked fields, approval
  rules). Unknown roles and permissions fail closed. A small API for routes: `require(permission)`,
  `scoped(query)`, `mask(record)`.
- **Masking:** strategies `initials`, `last4`, `city_only`, `day_only` for dates, applied in serializers by role.
- **Approvals (separation of duties):** declared in `policy.yaml`. Supports "actor must differ from the actor of
  an earlier step" and "N approvals from distinct approvers when a field exceeds a threshold". Refusals return
  403 with a code and are recorded in the audit log in their own transaction.
- **Audit log:** append-only table, hash-chained (`prev_hash`, `hash`), written in the same transaction as the
  change, SQLite triggers blocking UPDATE and DELETE, `GET /audit` (paged, filter by record) and
  `GET /audit/verify`. No personal data in entries.
- **Paging:** one helper for server-side paging with allowlisted sorting and exact totals.
- **Health:** `GET /health` returning app status and record counts.
- A test-only app under `backend/tests/` that proves FND-2: policy, scope, masking and approvals work from YAML
  alone.

Frontend (`web/src/platform/`):
- Design system on Tailwind and shadcn/ui: buttons, inputs, select, badge, card, dialog, toast, side sheet,
  skeletons, empty state.
- **App shell:** top bar with app switcher (Home, KYC), persona switcher with a DEV ONLY badge, page header.
- **Data table:** server-side paging, sorting, filters, "1–50 of 50,000", loading and empty states.
- **Record sheet:** side panel layout for record detail with an actions area and a history timeline.
- **Audit view:** paged list with filters and a "Verify chain" button showing the result.
- **Errors:** every API refusal shown as a toast with its code and message.
- **Home:** one card per app with name, owner team, short description, live health, record count and audit chain
  status, linking to the app.

Repo:
- `Makefile` targets from `AGENTS.md`, `.github/workflows/ci.yml` (ruff, pytest, eslint, tsc, build,
  Playwright), `scripts/foundation_diff.py` run in CI, and the README "Run it" section.

## PR 2: KYC Review Queue

Backend (`backend/apps/kyc/`):
- **Case:** reference (`TEST-KYC-000001`), applicant name, date of birth, ID number, address, country, risk
  (low, medium, high), screening result (clear, possible match, match), status (new, in review, recommended,
  approved, rejected), assignee, recommender and recommendation with a note, decider and decision, timestamps,
  version for optimistic locking.
- **Roles in `policy.yaml`:**
  - analyst: their assigned countries only, personal data masked, can claim and recommend
  - senior reviewer: all countries, unmasked (each unmasked read audited), can claim, recommend and decide
  - auditor: read-only, masked, can view and verify the audit log
- **Workflow:** claim → recommend (approve or reject, with a note) → decide. Whoever recommended a case cannot
  decide it.
- **Seed:** 50,000 cases across 6 countries, realistic mixes of status, risk and screening result; personas: two
  analysts with different countries, two senior reviewers, one auditor. Seeding finishes in under a minute.
- `make bench` reporting p95 for list, filter and search.

Frontend (`web/src/apps/kyc/`):
- **Queue:** the data table with filters (status, country, risk, screening result) and search by reference.
- **Case sheet:** applicant details as the current role may see them, screening result, the case's audit
  history, and actions for the current role (Claim, Recommend, Decide). Show Decide to senior reviewers even on
  cases they recommended, so the API's `SOD_VIOLATION` refusal is visible in the demo.
- Audit view for senior reviewers and auditors.

Tests: every id under Foundation, Privacy, Oversight and Scale in `docs/ACCEPTANCE.md`. Playwright: analyst
claims and recommends; the same person as senior reviewer is refused on Decide; a different senior reviewer
decides; the audit chain verifies.

## Out of scope

Real SSO, vendor webhooks, retention or purge, deployment, the Refunds app, dashboards or charts, an admin
console, app catalogs or app-creation flows, exports, email notifications, dark mode, mobile layouts. If you
think one of these is needed, list it as a follow-up.
