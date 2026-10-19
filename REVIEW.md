# REVIEW.md

What a reviewer (human or Devin Review) checks on every PR. Most bugs in tools like these are a control that
works on one path and not another.

1. **Sign-in fails closed.** Without `APP_ENV=dev` the mock header is ignored and authenticated endpoints return
   401. Unknown users and unknown roles are refused.
2. **Every endpoint calls the policy engine.** No route reads or writes data without a permission check.
3. **Row scope applies everywhere.** Lists, counts, search, lookups by id and exports all go through the scope
   helper. An out-of-scope record returns 404, not 403, so its existence is not revealed.
4. **Masking happens in the API.** Masked fields never leave the server for roles that should not see them.
   Unmasked reads, where allowed, are audited.
5. **Separation of duties is enforced in the service layer.** The person who recommends or requests cannot
   decide or approve. Where two approvals are required, they come from two different people. Attempts are
   refused with a clear code and recorded.
6. **The audit log is complete and tamper-evident.** Each state change writes its audit entry in the same
   transaction. Entries are hash-chained, database triggers block UPDATE and DELETE, and the verify endpoint
   detects an edited row. No personal data in audit entries.
7. **Lists are bounded and correct.** Server-side paging with exact totals; walking every page returns every
   row once. Sorting only by allowlisted columns. No N+1 queries on list pages.
8. **Tests prove the acceptance ids the PR claims.** Each id in `docs/ACCEPTANCE.md` has a test with that id in
   its name or docstring.
9. **The foundation stays put.** App PRs change nothing under `backend/platform/` or `web/src/platform/`, or the
   change is in a separate `platform:` commit that the PR explains.
10. **No scope creep, no secrets.** Nothing outside the session prompt; no keys, tokens or real data in the repo.
