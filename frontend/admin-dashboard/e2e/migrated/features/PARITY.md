# Parity: Selenium `FeaturesTest` → Playwright `features.spec.ts`

Legacy source: `tests/legacy-suites/selenium/src/test/java/com/otterworks/legacy/admin/tests/FeaturesTest.java`
(supporting: `AdminTestBase.java`, `pages/BasePage.java`, `pages/FeaturesPage.java`, `pom.xml`) on
`qe/legacy-suites-fixture`, run unmodified from a detached worktree with
`ADMIN_BASE_URL=http://localhost:4200 mvn -s frontend/admin-dashboard/e2e/migrated/stack/maven-settings.xml -Dtest=FeaturesTest test`
(Selenium 4.21, TestNG 7.10, headless Chrome) against the real local stack (Compose backend: postgres, redis,
localstack, auth, document, file, api-gateway, admin-service; `ng serve` on :4200, `/api` proxied to :8080).
Result: `Tests run: 3, Failures: 2`.

Why the legacy suite fails: `AdminTestBase` starts a fresh ChromeDriver and never signs in. `/features` sits behind
`authGuard` (`src/app/core/guards/auth.guard.ts`), which redirects to `/login` when `ow_admin_token` is absent. A fresh
headless browser opening `/features` on this stack lands on `http://localhost:4200/login` with no token, h1
`OtterWorks Admin` and zero `.flag-card` elements, so the legacy XPath locators find nothing.

Playwright: `npm run test:e2e:migrated -- --grep @selenium-FeaturesTest` (config `playwright.migrated.config.ts`),
run twice in a row against the same stack with identical results (3 passed, 3 passed). Each test gets a freshly
registered gateway user (`adminTest` → `signInAdminSession`) and proves the session came from the real gateway with
`expectGatewaySession` (token and user id match the registration response; id is not the offline mock id), and the
page's own `GET /api/v1/admin/features` must return 200. Flags are seeded through `POST /api/v1/admin/features` and
deleted in teardown. No route mocks.

| Legacy ID | Legacy name | Legacy source | What the legacy test did | Legacy result vs current app | Playwright test (file › title) | What the Playwright test does | Playwright result | Verdict | Decision and reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SEL-FeaturesTest-featurePageShowsHeading | featurePageShowsHeading | `FeaturesTest.java#featurePageShowsHeading` | Opens `/features` without signing in, sleeps 700 ms, reads `//h1[normalize-space()='Feature Flags']` and asserts its text equals `Feature Flags`. | Failed: `NoSuchElementException` for `//h1[normalize-space()='Feature Flags']`; the unauthenticated browser was redirected to `/login` (h1 `OtterWorks Admin`). | `features/features.spec.ts › SEL-FeaturesTest-featurePageShowsHeading featurePageShowsHeading` | Signs in a fresh gateway user, opens `/features` (URL stays `/features`, features API 200, gateway session proven) and asserts the level-1 heading has text `Feature Flags`. | Passed (run 1 and run 2) | legacy wrong | The heading exists and reads `Feature Flags` (`features.component.ts`). The legacy test never authenticates, so it can only ever see the login page; conversion adds a real gateway session and keeps the legacy expected text verbatim. |
| SEL-FeaturesTest-featureSearchCanBeApplied | featureSearchCanBeApplied | `FeaturesTest.java#featureSearchCanBeApplied` | Opens `/features` without signing in, clears and types `search` into the input with placeholder `Search by name or description`, sleeps, and asserts only that the input's value is `search`; it never checks the flag list. | Failed: `NoSuchElementException` for `//input[@placeholder='Search by name or description']` (redirected to `/login`). | `features/features.spec.ts › SEL-FeaturesTest-featureSearchCanBeApplied featureSearchCanBeApplied` | Seeds two flags (`a_features_search_<hex>` matching the term, `a_features_other_<hex>` not matching), opens `/features`, sees both cards, fills the `Search features` textbox with `search`, asserts the value is `search` (legacy assert) and then that the matching flag's card heading is still shown while the non-matching one is gone. | Passed (run 1 and run 2) | legacy wrong | Legacy fails for the auth reason above, and its body proves less than its name: an input holding typed text says nothing about the search being applied. Playwright keeps the legacy assert and adds the promised outcome (list filtered by name/description/key, `filteredFlags` in the component). Input located by its label, not the placeholder. |
| SEL-FeaturesTest-featureToggleCanBeSelected | featureToggleCanBeSelected | `FeaturesTest.java#featureToggleCanBeSelected` | Opens `/features` without signing in; only `if (featureCount() > 0)` it clicks the first `.flag-card mat-slide-toggle`, sleeps, and asserts the card count is still > 0. It never checks the toggle state, and with no cards it runs no assertion at all. | Passed, but vacuously: on `/login` there are 0 `.flag-card` elements, so the `if` body (click and assert) never ran. False pass. | `features/features.spec.ts › SEL-FeaturesTest-featureToggleCanBeSelected featureToggleCanBeSelected` | Seeds a disabled flag `a_features_toggle_<hex>`, opens `/features`, filters the list to that flag so exactly one switch remains, asserts it is unchecked, clicks it, requires the page's `PUT /api/v1/admin/features/<id>` to return 200, then asserts the switch is checked, the API reports `enabled: true`, and after reloading the page the flag's switch is still checked. | Passed (run 1 and run 2) | legacy wrong | The legacy pass proves nothing (no assertion executed; even when it runs, a card count > 0 does not show the toggle changed). Conversion removes the conditional by seeding the flag and asserts the promised outcome: the flag is toggled on and persisted. |

## Notes for the cross-check

- Locators: `getByRole('heading', { level: 1, name: 'Feature Flags' })`, `getByRole('textbox', { name: 'Search features' })`
  (mat-label), flag cards by their `getByRole('heading', { level: 3, name })`. Accessibility gap: each
  `mat-slide-toggle` renders `role=switch` with no accessible name and the card has no role, so the switch is reached
  by searching for the flag's unique name and asserting exactly one `getByRole('switch')` remains.
- The Features page only shows the first page of `GET /api/v1/admin/features` (ordered by name, default
  `per_page` 20, no paging UI). Seeded names start with `a_` so they land on page 1 even when other suites leave flags
  behind. If more than 20 flags sort before them, the seeded cards would not render; this is an app limitation, not
  hidden by the test.
- `FeaturesComponent.toggleFlag` computes `!flag.enabled` but never writes the new state back to `flag`. Probe on
  this stack (not committed): clicking a disabled flag's switch twice sent `{"feature":{"enabled":true}}` both times,
  leaving the switch unchecked while the API reports `enabled: true`. The legacy test clicks once, so this is out of
  scope for this module and not asserted; a candidate app defect for whoever owns toggle-off coverage.
- Legacy data kept verbatim in `fixtures.ts` (`FeaturesLegacyData`): route `/features`, heading `Feature Flags`,
  search term `search`, and the legacy placeholder identity `Search by name or description` (not used as a locator).
