# Session 2: Refunds Desk

Read `AGENTS.md`, `REVIEW.md` and `docs/ACCEPTANCE.md` first. They are part of this prompt.

## Context

The foundation and the KYC Review Queue are merged on `main`. Build the second app, the Refunds Desk, on the
same foundation. The point of this session is to show what a new app costs once the foundation exists, so it must
change **0 lines** under `backend/platform/` and `web/src/platform/`. If you believe a foundation change is
needed, stop and ask me first.

Use what is already there:

- **Registration:** add a manifest in `backend/apps/refunds/app.py` (same shape as `backend/apps/kyc/app.py`), list
  it in `backend/apps/__init__.py`, and add the web app to `web/src/apps/registry.ts`. Routes, Home card, app
  switcher, health and seeding then pick it up.
- **Policy:** declare everything in `backend/apps/refunds/policy.yaml`. Masking strategies available today are
  `initials`, `last4`, `city_only` and `day_only`. Approval rules follow the test app in
  `backend/tests/testapp/policy.yaml`: `distinct_from` plus a `count` rule above a threshold.
- **Approvals:** the engine evaluates; the app stores who approved. Keep approvals in a child table and call
  `check_separation` and `approvals_complete` from the service, the way the test app does.
- **Personas:** seed them with `upsert_user` and a `RoleAssignment` for app `refunds`. Give Elena Vega (already the
  KYC auditor) the auditor role in Refunds too, so one person holds roles in both apps.
- **UI:** reuse `DataTable`, `RecordSheet`, `AuditView` and the components in `web/src/platform/ui`, following the
  structure of `web/src/apps/kyc/`.

## Process

1. Post a plan with your estimated ACUs and wall-clock time, then wait for my approval. Aim for about 30 minutes.
2. Build it as one PR. Its description lists acceptance ids, checks run, the foundation diff output, the ACUs
   used and wall-clock time, and follow-ups.
3. If you expect to go more than 25% over your estimate, stop and tell me why.

## What to build

Backend (`backend/apps/refunds/`):
- **Refund:** reference (`TEST-RFD-000001`), customer name, card last 4 digits (store only the 4 digits, never a
  full card number), amount in cents (USD), type (goodwill or dispute), reason, date the customer reported it
  (for disputes), region, status (requested, pending second approval, approved, paid, rejected), requester,
  rejecter, timestamps, version. Approvals in a child table (approver, time).
- **Roles in `policy.yaml`:**
  - agent: their regions only, customer name masked (`initials`), can request refunds
  - approver: all regions, can request, approve or reject (so an approver who requested a refund is refused
    with `SOD_VIOLATION`, not a generic permission error)
  - finance: all regions, can mark approved refunds as paid
  - auditor: all regions, read-only, customer name masked, can view and verify the audit log
- **Rules in `policy.yaml`:** the requester cannot approve their own refund; refunds above $5,000 need two
  approvals from two different approvers; an approver cannot approve the same refund twice.
- **Workflow:** request → approve (stays "pending second approval" until the rule is met) → paid, or reject from
  requested or pending. Every transition is one service function with version check, separation check, audit
  entry and commit, as in KYC.
- **Seed:** 20,000 refunds across 4 regions, about a third disputes, realistic amounts (most under $1,000, some
  above $5,000), a few hundred with full approval history. Personas: two agents with different regions, two
  approvers, one finance user, and Elena as auditor.

Frontend (`web/src/apps/refunds/`):
- **Queue:** data table with filters (status, type, region) and search by reference. Open on work to do
  (requested and pending second approval), oldest first.
- **Refund sheet:** customer details as the current role may see them, amount, type, reason, an approvals
  timeline, the audit history with people's names and plain labels, and actions for the current role (Approve,
  Reject, Mark paid). Show Approve to approvers even on refunds they requested or already approved, so the API
  refusal is visible.
- **New refund** form for agents.
- Audit log tab for approvers and auditors, as in KYC.

Tests: REP-1 to REP-5 in `docs/ACCEPTANCE.md`. Playwright (`web/e2e/refunds.spec.ts`): an agent requests a
$7,500 refund; an approver approves and it stays pending; the same approver is refused a second approval; a
second approver approves; finance marks it paid; the audit chain verifies. A second test: an approver requests a
refund and is refused with `SOD_VIOLATION` when approving it.

## Out of scope

Anything not listed above, including dashboards, exports, payment provider integrations, notifications and any
change to the foundation.
