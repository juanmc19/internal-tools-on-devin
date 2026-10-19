# Devin sessions

Three sessions, one prompt each. Each session ends in reviewed PRs and a row in `docs/RECEIPTS.md`.

| Session | Prompt | Builds | Target Devin time |
|---|---|---|---|
| 1 | [session-1-foundation-kyc.md](session-1-foundation-kyc.md) | PR 1 foundation, PR 2 KYC Review Queue | ~65 min |
| 2 | [session-2-refunds.md](session-2-refunds.md) | PR 3 Refunds Desk | ~30 min |
| 3 | [session-3-reg-e-request.md](session-3-reg-e-request.md) | PR 4 Reg E deadlines | ~15 min |

## Before session 1

1. Push `AGENTS.md`, `REVIEW.md`, `README.md` and `docs/` to `main`.
2. In Devin, connect the repo and turn on Devin Review for it.
3. Raise the per-message usage limit to about $40 for the build sessions.
4. Note the on-demand usage figure and the time. Do the same at the end of each session.

## During each session

- Approve or push back on Devin's plan before any code. One pushback round, then go.
- Review each PR against `REVIEW.md`. Merge only with CI green and Devin Review findings handled.
- Write down every intervention and every real bug that Devin or Devin Review missed.
