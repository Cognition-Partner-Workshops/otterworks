# Parity: Selenium `UsersTest` → Playwright `users.spec.ts`

Legacy source: `tests/legacy-suites/selenium/src/test/java/com/otterworks/legacy/admin/tests/UsersTest.java`
(supporting: `AdminTestBase.java`, `pages/BasePage.java`, `pages/UsersPage.java`, `pom.xml`).

Legacy run: `ADMIN_BASE_URL=http://localhost:4200 mvn -s frontend/admin-dashboard/e2e/migrated/stack/maven-settings.xml test -Dtest=UsersTest`
from a worktree of `origin/qe/legacy-suites-fixture`, against the real local Compose stack + `ng serve` on :4200
(Maven 3.9.9, Java 17, Chrome 156 via Selenium Manager): 3 run, 0 passed, 3 failed.

Root cause of every legacy failure: `AdminTestBase` starts a fresh headless Chrome and never signs in, and
`/users` is behind `authGuard` (`src/app/app.routes.ts`), so the browser is redirected to `/login` (verified:
an unauthenticated browser opening `/users` lands on `/login`, whose only `h1` is "OtterWorks Admin").
The Users page itself is unchanged: its `h1`, search input and Role select are all in
`src/app/pages/users/users.component.ts`.

Playwright: `npx playwright test --config playwright.migrated.config.ts --grep @selenium-UsersTest`, real stack,
two consecutive runs, 3/3 passed both times. Every test signs in a fresh gateway user (`adminTest` /
`signInAdminSession`), waits for `GET /api/v1/admin/users` sent with that user's bearer token (200), and calls
`expectGatewaySession`, so the offline `AuthService.mockLogin` path cannot satisfy it. No route mocks.

| Legacy ID | Legacy name | Legacy source | What the legacy test did | Legacy result vs current app | Playwright test (file › title) | What the Playwright test does | Playwright result | Verdict | Decision and reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SEL-UsersTest-userListShowsHeading | userListShowsHeading | UsersTest.java#userListShowsHeading | Opened `/users` without signing in, slept 700 ms, read the `h1` found by XPath `//h1[normalize-space()='User Management']` and asserted it equals "User Management". | Failed: `NoSuchElementException` for the `h1` XPath — redirected to `/login` because the test never authenticates. | `e2e/migrated/users/users.spec.ts › SEL-UsersTest-userListShowsHeading userListShowsHeading` | Signs in a fresh gateway user, opens `/users`, proves the real users API call and gateway session, asserts the level-1 heading has text "User Management". | Passed (2/2 runs) | legacy wrong | Converted. The legacy test cannot reach a guarded route; with a real session the heading is as promised. XPath dropped for `getByRole('heading', { level: 1 })`. |
| SEL-UsersTest-userSearchAcceptsText | userSearchAcceptsText | UsersTest.java#userSearchAcceptsText | Opened `/users` without signing in, cleared + typed "alex" into the input found by placeholder XPath "Search by name or email", slept, asserted the input value is "alex". Never checked the list. | Failed: `NoSuchElementException` for the placeholder XPath — redirected to `/login`. | `e2e/migrated/users/users.spec.ts › SEL-UsersTest-userSearchAcceptsText userSearchAcceptsText` | Signs in a fresh gateway user, opens `/users` (real API + session proven), fills the textbox named "Search users" (its `mat-label`) with "alex", asserts it has value "alex". | Passed (2/2 runs) | legacy wrong | Converted. The name promises that the search field accepts text, which is what both sides assert. Difference recorded: neither side proves the list is filtered — the Users table is empty on a fresh stack and `admin_users` has no create API (only `scripts/seed.py` direct DB insert of shared fixed users), so a per-test real-API seed of rows to filter is impossible; filtering coverage is a gap for the cross-check. Placeholder kept only as `LegacySearchPlaceholder` data. |
| SEL-UsersTest-roleFilterIsAvailable | roleFilterIsAvailable | UsersTest.java#roleFilterIsAvailable | Opened `/users` without signing in, slept, asserted that `//mat-label[normalize-space()='Role']/following::mat-select[1]` is present. Never opened or applied the filter. | Failed: `expected [true] but found [false]` — redirected to `/login`, so no Role select exists. | `e2e/migrated/users/users.spec.ts › SEL-UsersTest-roleFilterIsAvailable roleFilterIsAvailable` | Signs in a fresh gateway user, opens `/users` (real API + session proven), opens the combobox named "Role", asserts the "Role" listbox offers exactly All Roles, Admin, Editor, Viewer. | Passed (2/2 runs) | legacy wrong | Converted. "Available" is asserted as usable (opens and offers the role options from `users.component.ts`), stronger than legacy presence-only. Applying the filter is not asserted: no Users rows can be seeded through the real API (same gap as above). `mat-*` XPath dropped for `getByRole('combobox', { name: 'Role' })`. |
