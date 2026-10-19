# Receipts

What each session cost. Devin spend is read from the Devin usage page before and after each session: on-demand
usage went from $58.70 (before session 1) to $78.89, $87.86 and $94.34, and the remaining balance dropped by the
same amounts. The daily quota was already used up before session 1, so every session was billed on demand. Wall
clock comes from the session timestamps and is also in each PR description.

| Session | What it built | Devin spend | Wall clock | Interventions | Review findings | Foundation lines changed |
|---|---|---|---|---|---|---|
| 1 | Foundation + KYC Review Queue ([#1](https://github.com/juanmc19/internal-tools-on-devin/pull/1), [#2](https://github.com/juanmc19/internal-tools-on-devin/pull/2)) | $20.19 | ~45 min | 2 | 3, all fixed before merge | n/a (built it); KYC: 0 |
| 2 | Refunds Desk ([#3](https://github.com/juanmc19/internal-tools-on-devin/pull/3)) | $8.97 | ~16 min from plan approval to PR (estimate ~35) | 0 | 0 | 0 |
| 3 | Reg E deadline request ([#4](https://github.com/juanmc19/internal-tools-on-devin/pull/4)) | $6.48 | ~11 min to PR, ~13 to green CI | 0 | 0 | 0 |
| **Total** | Two apps on one foundation, plus a change request | **$35.64** | **~72 min** | 2 | 3 | |

Devin spend is Devin's cost only; it doesn't include the engineer time spent reviewing. Session 1 was reviewed by
reading the code against [REVIEW.md](../REVIEW.md). Sessions 2 and 3 were reviewed by running them: the tests, the
live approval flows and refusals, and the Reg E deadline math checked by hand.

## Bugs Devin missed

- **Audit-chain race under concurrent writes (PR #1).** `audit.last_hash()` ran before SQLite took the write
  lock (pysqlite only issues `BEGIN` at the first `INSERT`), so two concurrent writers could chain to the same
  previous hash and `/audit/verify` would report a false break. Caught in review; fixed before merge by
  starting every write transaction with `BEGIN IMMEDIATE`, with a threaded test.

## Interventions

- **Session 1, plan:** pushed back on the plan before approving it (time box, seeded audit history, shadcn/ui,
  persona labels).
- **Session 1, review:** sent three fixes after the PRs opened: the audit-chain race above, the queue's default
  filter, and plain labels in the case history.
- **Session 2:** none beyond approving the plan.
- **Session 3:** none; the prompt told Devin to build without waiting for approval.

Not counted as interventions:

- Session 1 fixed one CI failure on its own: Playwright timed out because Vite bound to IPv6 localhost, and
  Devin set `server.host` to `127.0.0.1`.
- Changes made to a prompt before its session started are in the prompt files under
  [docs/devin-sessions](devin-sessions).

## Notes

- A blueprint (saved environment setup) was approved after session 1, but its snapshot failed to build, so
  session 2 ran without it. Session 2's lower cost comes from reusing the foundation, not from saved setup.
