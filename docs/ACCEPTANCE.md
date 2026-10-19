# Acceptance criteria

Each claim the prototype makes, the tests that prove it, and the step that shows it in the demo. Put the id
(for example `PRIV-2`) in the test name or docstring.

## Foundation (session 1, PR 1)

| Id | Criterion | Proven by |
|---|---|---|
| FND-1 | Without `APP_ENV=dev`, every authenticated endpoint returns 401; unknown users and roles are refused | pytest |
| FND-2 | An app's roles, permissions, row scope, masked fields and approval rules are declared in its `policy.yaml`; the foundation enforces them with no app-specific code | pytest with a test-only app |
| FND-3 | `make setup && make seed && make run && make web` works on a fresh clone with Python 3.12 and Node 20 | CI and README |
| FND-4 | The app shell has a persona switcher (marked DEV ONLY), an app switcher (Home, KYC, Refunds) and shows API refusals with their code | Playwright |
| FND-5 | `scripts/foundation_diff.py` prints the lines changed under `backend/platform/` and `web/src/platform/` against `main`; CI runs it on every PR | CI log |

## Privacy (KYC)

| Id | Criterion | Proven by |
|---|---|---|
| PRIV-1 | An analyst sees applicants' names as initials, ID numbers as the last 4 digits and addresses as city only, in every response | pytest |
| PRIV-2 | An analyst sees only cases in their assigned countries; another country's case returns 404, and lists and counts exclude it | pytest |
| PRIV-3 | An analyst asking for unmasked data gets 403 `PII_MASKED_FOR_ROLE`; a senior reviewer's unmasked read writes an audit entry | pytest |

## Oversight (KYC)

| Id | Criterion | Proven by |
|---|---|---|
| OVR-1 | The reviewer who recommended a case cannot decide it: 403 `SOD_VIOLATION`, the case is unchanged, and the attempt is recorded | pytest, Playwright |
| OVR-2 | Every state change writes its audit entry in the same transaction; if the change fails, no entry is written | pytest |
| OVR-3 | Audit entries are hash-chained; a database trigger blocks UPDATE and DELETE; `GET /audit/verify` names the first edited row on a tampered copy | pytest |
| OVR-4 | The audit view lists entries for a case and has a "Verify chain" button that shows the result | Playwright |

## Scale (KYC)

| Id | Criterion | Proven by |
|---|---|---|
| SCL-1 | With 50,000 seeded cases, the queue shows the exact total for any filter ("1–50 of 50,000") | pytest |
| SCL-2 | Walking every page returns every case exactly once | pytest |
| SCL-3 | List and search requests stay under 300 ms at p95 locally; `make bench` prints the numbers | benchmark script |

## Repeatable (Refunds, session 2)

| Id | Criterion | Proven by |
|---|---|---|
| REP-1 | Refunds gets sign-in, roles, row scope, masking, approvals and the audit log from the foundation | pytest |
| REP-2 | A requester cannot approve their own refund: 403 `SOD_VIOLATION` | pytest, Playwright |
| REP-3 | Refunds above $5,000 need two approvals from two different approvers; the first approval leaves the refund pending | pytest, Playwright |
| REP-4 | Only the last 4 digits of a card are stored; customer names are masked for agents | pytest |
| REP-5 | The Refunds PR changes 0 lines of the foundation, or reports each changed line in a `platform:` commit | foundation diff in CI |

## Tailored (Refunds, session 3)

| Id | Criterion | Proven by |
|---|---|---|
| TLR-1 | Each dispute shows business days left before its Reg E deadline (10 business days from when the customer reported it; weekends and US federal holidays excluded) | pytest |
| TLR-2 | The queue can be sorted by most urgent deadline, and overdue disputes are flagged | pytest, Playwright |
| TLR-3 | Goodwill refunds show no deadline | pytest |
| TLR-4 | No foundation lines changed; existing tests still pass | CI |

## Demo path (about 1:45)

1. Devin's approved plan and the merged PRs.
2. KYC as an analyst: masked data, own countries only, "of 50,000" (PRIV-1, PRIV-2, SCL-1).
3. Recommend a case, then try to decide it as the same person: `SOD_VIOLATION`. Switch to another senior reviewer
   and decide. Open the audit view and verify the chain (OVR-1, OVR-4).
4. Refunds: same shell. A $7,500 refund stays pending after one approval and is blocked for its requester
   (REP-2, REP-3). Foundation diff: 0 lines (REP-5).
5. The ops lead's Reg E request and its PR, with the deadline column live (TLR-1, TLR-2).
6. Receipts from `docs/RECEIPTS.md`.
