# Session 2: Refunds Desk

Read `AGENTS.md`, `REVIEW.md` and `docs/ACCEPTANCE.md` first. They are part of this prompt.

## Context

The foundation and the KYC Review Queue are merged. Build the second app, the Refunds Desk, on the same
foundation. The point of this session is to show what a new app costs once the foundation exists, so work only
in `backend/apps/refunds/` and `web/src/apps/refunds/`, plus registering the app (routes, Home card, app switcher
entry, seed and CI). Do not change `backend/platform/` or `web/src/platform/`. If you believe a foundation change
is needed, stop and ask me first.

## Process

1. Post a plan with your estimated cost and wait for my approval.
2. Build it as one PR. Its description lists acceptance ids, checks run, the foundation diff output, and
   follow-ups.
3. If you expect to go more than 25% over your estimate, stop and tell me why.

## What to build

Backend (`backend/apps/refunds/`):
- **Refund:** reference (`TEST-RFD-000001`), customer name, customer email, card last 4 digits (never a full card
  number), amount in USD, type (goodwill or dispute), reason, date the customer reported it (for disputes),
  region, status (requested, pending second approval, approved, paid, rejected), requester, approvals (approver
  and time), rejecter, timestamps, version.
- **Roles in `policy.yaml`:**
  - agent: their regions only, customer name and email masked, can request refunds
  - approver: all regions, can approve or reject
  - finance: all regions, can mark approved refunds as paid
  - auditor: read-only, masked, can view and verify the audit log
- **Rules in `policy.yaml`:** the requester cannot approve their own refund; refunds above $5,000 need two
  approvals from two different approvers; an approver cannot approve the same refund twice.
- **Seed:** 20,000 refunds across 4 regions, about a third disputes; personas: two agents with different
  regions, two approvers, one finance user, one auditor.

Frontend (`web/src/apps/refunds/`):
- **Queue:** data table with filters (status, type, region, amount range) and search by reference.
- **Refund sheet:** customer details as the current role may see them, amount, type, reason, an approvals
  timeline, the audit history, and actions for the current role (Request, Approve, Reject, Mark paid). Show
  Approve to approvers even on refunds they requested, so the API refusal is visible.
- **New refund** form for agents.
- Home card and app switcher entry.

Tests: REP-1 to REP-5 in `docs/ACCEPTANCE.md`. Playwright: an agent requests a $7,500 refund; an approver
approves and it stays pending; the same approver is refused a second approval; a second approver approves; finance
marks it paid.

## Out of scope

Anything not listed above, including dashboards, exports, payment provider integrations and notifications.
