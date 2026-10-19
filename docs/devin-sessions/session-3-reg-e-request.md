# Session 3: a request from the Payments Ops lead

Read `AGENTS.md`, `REVIEW.md` and `docs/ACCEPTANCE.md` first. They are part of this prompt.

## The request, as it arrived

> We keep getting close to the Reg E deadline on disputes because nothing in the queue shows it. Can each dispute
> show how many business days are left before the deadline? It's 10 business days from when the customer
> reported it. I'd like to sort the queue by whatever is most urgent and see overdue ones flagged in red.
> Goodwill refunds don't have a deadline.

## Engineering notes

- Work only in `backend/apps/refunds/` and `web/src/apps/refunds/`. No foundation changes.
- Business days exclude weekends and US federal holidays. Keep the holiday list in one place and test it.
- Compute the deadline on the server and return it with each dispute; sort on the server.
- Tests: TLR-1 to TLR-4 in `docs/ACCEPTANCE.md`, including a deadline that spans a weekend and one that spans a
  holiday. Update the refunds Playwright test to sort by deadline and see an overdue flag.
- One PR. Post a short plan with your estimate first, then build without waiting unless something is unclear.
