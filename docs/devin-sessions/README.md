# Devin sessions

The prototype was built in three Devin sessions, one prompt each, followed by a security pass. Each prompt below
is the one Devin was given; [RECEIPTS.md](../RECEIPTS.md) has the cost, time and review findings for each.

| Session | Prompt | Result | Time |
|---|---|---|---|
| 1 | [Foundation and KYC Review Queue](session-1-foundation-kyc.md) | [#1](https://github.com/juanmc19/internal-tools-on-devin/pull/1) foundation, [#2](https://github.com/juanmc19/internal-tools-on-devin/pull/2) KYC Review Queue | ~45 min |
| 2 | [Refunds Desk](session-2-refunds.md) | [#3](https://github.com/juanmc19/internal-tools-on-devin/pull/3) Refunds Desk, no foundation changes | ~16 min |
| 3 | [Reg E change request](session-3-reg-e-request.md) | [#4](https://github.com/juanmc19/internal-tools-on-devin/pull/4) Reg E deadlines, no foundation changes | ~11 min |
| Security | Started from Devin's security scan, not a prompt file | [#9](https://github.com/juanmc19/internal-tools-on-devin/pull/9)–[#16](https://github.com/juanmc19/internal-tools-on-devin/pull/16), 9 findings fixed | |

## How each session ran

1. Devin read [AGENTS.md](../../AGENTS.md), [REVIEW.md](../../REVIEW.md) and [ACCEPTANCE.md](../ACCEPTANCE.md),
   which every prompt names as part of the prompt.
2. Devin proposed a plan, and the plan was approved before any code. Session 3's prompt asked Devin to build
   without waiting, the way a routine change request would run.
3. Devin built and tested in its own cloud machine (API, web app and Playwright browser tests), then opened PRs.
4. Each PR was reviewed against REVIEW.md and merged with CI green. Interventions and bugs Devin missed are
   recorded in RECEIPTS.md.
