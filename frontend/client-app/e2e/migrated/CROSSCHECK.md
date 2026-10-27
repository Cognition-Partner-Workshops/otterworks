# Cross-check decisions: legacy Selenium + Cypress conversions vs. each other and the Tosca conversion

Round 2 ran before anything was combined. Three independent reviewers read all 9 module branches, the shared admin scaffold and the Tosca conversion (qe/tosca-to-playwright, plus the Tosca Documents/Authentication/Search folders still open in #2234/#2235/#2236). Each finding below has a decision. Findings evidence is summarized in the rationale attached to each decision.

## Duplicate journeys

| ID | Finding | Decision |
|---|---|---|
| DUP-01 | qe/tosca-to-playwright already has Settings, Sharing and the Templates retirement. Authentication and Search are only in open PRs #2235/#2236. Checking against Documents alone would miss duplicates. | **Accepted.** The combined branch is based on qe/tosca-to-playwright, with #2234, #2235 and #2236 merged in, so each legacy test is compared with the Tosca test it duplicates. The PR diff shows their commits until they merge. |
| DUP-02 | CY-sign-in-01 (valid sign-in → dashboard) duplicates TC-AUTH-001. | **Merged** into `authentication.spec.ts › TC-AUTH-001`. That test gains `@CY-sign-in-01` tags, the cypress annotation, and the Cypress-only check (the user's display name shows on /dashboard). The separate Cypress copy is removed. |
| DUP-03 | CY-sign-in-02 (empty email) vs TC-AUTH-002 (malformed email). | **Kept both.** They exercise different validators (Zod "Please enter a valid email" on an empty field vs. native typeMismatch on a malformed one). CY-sign-in-02 moves next to TC-AUTH-002 in `authentication.spec.ts`, and each test has a comment naming the other. |
| DUP-04 | CY-document-search-01 duplicates TC-SRCH-001 (find document by title). | **Merged** into `search.spec.ts › TC-SRCH-001`. That test gains the Cypress steps (visit `/search?q=quarterly`, result "Quarterly Planning", input value kept). The legacy data stays verbatim. |
| DUP-05 | CY-settings-01 duplicates TC-SET-003 (save profile name). Both hit the same app defect (client sends PATCH /auth/profile, auth-service maps only PUT). | **Merged** into `settings.spec.ts › TC-SET-003`. It stays `test.fail()` with one shared defect note. The Cypress value "Casey Taylor" and the displayName request-body check are added. |
| DUP-06 | CY-starred-01 duplicates TC-SHARE-003 (view starred documents). | **Merged** into `sharing.spec.ts › TC-SHARE-003`. `seedStarredDocument` returns `{userId, documentId}` and asserts the `otter_starred_items` entry. |
| DUP-07 | Admin dashboard login (SEL-LoginTest ×3) vs. client sign-in. | **Not a duplicate.** These are different apps and different journeys. All three are kept under `frontend/admin-dashboard/e2e/migrated/login/`. |
| DUP-08 | SEL-HealthTest summary vs. refresh both assert the initial summary. | **Kept both; trimmed.** The redundant `expectSummary` is removed from healthDataCanBeRefreshed STEP-01. The summary assertion stays in healthSummaryIsDisplayed. |
| DUP-09 | 8 copies of "register a fresh client user and store tokens". | **Consolidated** with PO-01. There is one `support/account.ts › registerUser`, and `support/accounts.ts` is deleted. |

## Shared page objects and helpers

| ID | Finding | Decision |
|---|---|---|
| PO-01 | Client account registration and session forked in 4 cypress fixtures + auth branch. | **Accepted, one name.** `registerUser(request, page?, opts)` in `support/account.ts` (backward compatible) returns `{id,email,displayName,password,accessToken,refreshToken,headers}` and stores tokens when `page` is given. There is no second `registerAccount` export. |
| PO-02 | Document creation duplicated. seedWorkspace signatures diverge between base and #2236. | **Accepted.** `support/workspace.ts` exports `createDocument`/`deleteDocument`. `seedWorkspace` adopts #2236's signature `(request, page, label = 'Documents') → {documents,total,headers,userId}` and is built on `registerUser`. |
| PO-03 | Search-indexing poll duplicated with different semantics. | **Accepted.** There is one exported `support/search.ts › waitForIndexedItem(request, headers, query, id, {type?, timeout?})`. |
| PO-04 | Star-via-UI duplicated. | **Accepted.** `support/sharing.ts` exports `starDocumentViaUi` and `expectStarredItem`. |
| PO-05 | Two sets of client Settings locators + duplicated defect marker. | **Accepted.** `support/settings-page.ts › SettingsPage` is used by settings.spec.ts. |
| PO-06 | Two sets of client /login locators. | **Accepted.** `support/login-page.ts › ClientLoginPage` + `signInThroughLoginForm` are used by authentication.spec.ts. |
| PO-07 | Inconsistent Legacy<Field> naming for account values. | **Accepted.** The names are always `LegacyUserId/UserId`, `LegacyEmail/Email`, `DisplayName`, `Password`. Legacy literals stay in the owning folder's fixtures. |
| PO-08 | Playwright's `use` fixture callback trips client ESLint `react-hooks/rules-of-hooks`. Workers renamed it to `provide`, so fixtures diverge from the reference. | **Accepted.** An ESLint override for `e2e/**/*.ts` only (tooling config, no app code) turns that rule off, and every fixture uses `use`. |
| PO-09 | Admin "open page + prove the real API call" implemented 4 ways, with uneven gateway proof. | **Accepted.** `support/admin-session.ts` exports `waitForAdminApi` and `openAdminPage`. Every admin page object opens through them, so every test proves the request carried the real gateway token (not the offline mock). |
| PO-10 | Admin mat-select filter and (keyup) search box duplicated. | **Accepted.** `support/material.ts` provides `matSelect(page,label)` and `typeIntoFilter(input,text)`, used by Audit and Users. |
| PO-11 | Admin /login locators duplicated between LoginPage and signInThroughLoginForm. | **Accepted.** LoginPage moves to `admin-dashboard/e2e/migrated/support/login-page.ts`, and the helper uses it. |
| PO-12 | Unique feature-flag names generated in 3 places. | **Accepted.** `uniqueFlagName(prefix)` in admin-session.ts. |
| PO-13 | Traceability tag/annotation boilerplate differs by spec. | **Accepted.** `support/traceability.ts` per app (`legacyDetails({suite,id,group,source,method?})`) is used by every migrated spec, Tosca and legacy alike. |

## Contradicting assertions

| ID | Finding | Decision |
|---|---|---|
| ASSERT-01 | The search input is located as a labelled textbox in Tosca Search and as an unnamed textbox in main in CY-document-search. Both can't be right. | **Evidence decides: the input has no label or aria-label; its only accessible name comes from the placeholder.** There is one shared search-input locator in `support/search.ts`, `getByRole('main').getByRole('textbox')`, with an a11y-gap comment, used by all search tests. The value assertions don't change. |
| ASSERT-02 | Angular `(keyup)` filter inputs: Users used `fill()`, Audit used `clear()+pressSequentially`. `fill()` sends no keyup, so the filter never runs. | **pressSequentially wins** (it is what triggers the app's filter). Both go through `typeIntoFilter` (PO-10). The `toHaveValue` assertions don't change. |

## Not raised by the reviewers, recorded here
- On a fresh stack the admin Users list is empty (admin_users has no create API). SEL-UsersTest stays limited to heading, search input and role filter, and the coverage gap is recorded in users/PARITY.md, not papered over.
- admin-service checks only the JWT signature, not roles. Any registered user can call admin endpoints. This is recorded as an app finding. App code is unchanged.
- Admin FeaturesComponent.toggleFlag never stores the new state, so a second toggle resends `enabled:true`. This is recorded, not asserted. It is out of scope for the legacy tests.
