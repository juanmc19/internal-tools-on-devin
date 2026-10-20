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

## Security pass

After the three sessions, Devin's security scan reviewed the whole repo. It reported 12 findings; triage merged
2 duplicates and left 10 open: 3 high priority, 7 medium, none critical. Nine were fixed. The tenth, making the
audit log tamper-evident against someone with direct database access (a keyed signature and an external
checkpoint), was left for production along with real Entra ID sign-in. Devin split the fixes across 6 sessions
running in parallel, one PR each, and Devin Review checked every PR.

| PR | Fix | Devin Review finding |
|---|---|---|
| [#9](https://github.com/juanmc19/internal-tools-on-devin/pull/9) | Address masking fails closed when there is no city | A unit like `Apt 4` was still shown as the city |
| [#10](https://github.com/juanmc19/internal-tools-on-devin/pull/10) | `X-Request-Id` is validated before it reaches audit rows | An alphanumeric id could still carry personal data |
| [#11](https://github.com/juanmc19/internal-tools-on-devin/pull/11) | Approval and separation-of-duties rules fail closed on a mistyped field; the strictest count wins | None |
| [#12](https://github.com/juanmc19/internal-tools-on-devin/pull/12) | `/health` and refusal logging no longer hold the SQLite write lock | None |
| [#13](https://github.com/juanmc19/internal-tools-on-devin/pull/13) | Roles without `audit.read` get a trimmed workflow timeline | Histories had no page limit |
| [#14](https://github.com/juanmc19/internal-tools-on-devin/pull/14) | Dev sign-in only from loopback; Reg E dates bounded and business days counted in constant time | The two-year cutoff was a day off across a leap year |
| [#15](https://github.com/juanmc19/internal-tools-on-devin/pull/15) | Fixes for the four findings above | A named unit like `Rear` was still shown as the city |
| [#16](https://github.com/juanmc19/internal-tools-on-devin/pull/16) | The city is stored in its own field and the street address is fully masked | None |

PRs #9 to #15 were merged before Devin Review finished, so each finding landed on `main` and was fixed in the
next PR; #16 was merged after a clean review. Most fixes are in the foundation, each in its own `platform:` commit.

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
