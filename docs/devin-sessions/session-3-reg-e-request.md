# Session 3: a request from the Payments Ops lead

Read `AGENTS.md`, `REVIEW.md` and `docs/ACCEPTANCE.md` first. They are part of this prompt.

## The request, as it arrived

> We keep getting close to the Reg E deadline on disputes because nothing in the queue shows it. Can each dispute
> show how many business days are left before the deadline? It's 10 business days from when the customer
> reported it. I'd like to sort the queue by whatever is most urgent and see overdue ones flagged in red.
> Goodwill refunds don't have a deadline.

## Engineering notes

- Work only in `backend/apps/refunds/`, `backend/tests/refunds/`, `web/src/apps/refunds/` and
  `web/e2e/refunds.spec.ts`. No foundation changes.
- Business days exclude weekends and US federal holidays. Keep the holiday list in one place and test it.
- Store the deadline date on each dispute when it is created (and in the seed), so the queue can sort and page by
  it on the server. Business days left is computed against today's date, which tests can fix.
- **Seed data:** today the seeded disputes' report dates sit weeks before the seed's base date, so almost every
  open dispute would show as overdue. Date the open disputes relative to the day the seed runs, so the queue
  shows a realistic mix: a few overdue, some due in the next 1 to 2 business days, most with time left. Closed
  refunds can stay as they are.
- README: add one line saying the prototype tracks only the 10-business-day Reg E deadline and does not model the
  provisional-credit extension to 45 or 90 days or the customer's 60-day reporting window.
- Tests: TLR-1 to TLR-4 in `docs/ACCEPTANCE.md`, including a deadline that spans a weekend and one that spans a
  holiday. Update the refunds Playwright test to sort by deadline and see an overdue flag.
- One PR. Post a short plan with your estimate first, then build without waiting unless something is unclear.
  Put the ACUs used and the wall-clock time in the PR description.
