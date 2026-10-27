# Cypress `settings.cy.js` parity

Legacy source: `tests/legacy-suites/cypress/cypress/e2e/settings.cy.js` (branch `qe/legacy-suites-fixture`),
supporting files `cypress.config.js`, `package.json`, `cypress/support/e2e.js` (`visitAsUser`),
`cypress/fixtures/user.json`, `cypress/fixtures/settings.json`. Playwright runs use the real local stack
(Compose backend + Vite on :3000) per [the runbook](../README.md); no route mocks.

| Legacy ID | Legacy name | Legacy source | What the legacy test did | Legacy result vs current app | Playwright test (file › title) | What the Playwright test does | Playwright result | Verdict | Decision and reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CY-settings-01 | updates the profile name | `tests/legacy-suites/cypress/cypress/e2e/settings.cy.js#updates the profile name` | Stubbed every `/api/v1/**` call (`cy.intercept`; `GET /auth/profile` and `PATCH /auth/profile` answered with `user.json`, `GET /settings` with `settings.json`), set a fake JWT via `visitAsUser`, visited `/settings`, waited on the `@settings` alias, cleared `#name`, typed `Casey Taylor`, clicked "Save changes", and asserted only that the outgoing PATCH body included `displayName: "Casey Taylor"`. It never checked the response, the UI or the stored profile, and no backend was involved. | Passed (1/1, `npx cypress run --spec cypress/e2e/settings.cy.js`, Cypress 13.17.0 against Vite :3000). A false pass: the stub answered the PATCH with 200, but the real auth-service answers it with HTTP 500. | `e2e/migrated/cypress-settings/cypress-settings.spec.ts › CY-settings-01 updates the profile name` | Registers a fresh, uniquely named user (display name `Alex Morgan` from `user.json`) through the real `/api/v1/auth/register`, stores its real tokens, opens `/settings`, waits for the profile form to show that user's name and email, clears and types `Casey Taylor` into "Full name", clicks "Save changes", asserts the real PATCH body carries `displayName: "Casey Taylor"` (legacy assertion) and returns 200, then asserts what the name promises: "Profile updated successfully." is shown, `GET /api/v1/auth/profile` returns `Casey Taylor`, and the field still holds it after a reload. | Expected failure (`test.fail()`), reported as passed, twice with identical results: STEP-01..05 pass, the legacy body assertion in STEP-06 passes, then `PATCH /api/v1/auth/profile status` expected 200, received 500. | app defect | Kept as a failing test marked `test.fail()`; app code not changed (golden-app policy). Evidence: the client's `authApi.updateProfile` (`src/lib/api.ts`) sends `PATCH /auth/profile`, but auth-service `AuthController` maps only `@PutMapping("/profile")` (and `docs/api-route-matrix.md` documents `PUT /api/v1/auth/profile`). The auth-service log shows `HttpRequestMethodNotSupportedException: Request method 'PATCH' is not supported`, which `GlobalExceptionHandler`'s catch-all turns into HTTP 500. A direct `PUT` with the same body returns 200 and saves the name, so the backend works and the client uses the wrong method. The Settings page has no `onError` handling, so the user gets no message and the name is not saved. The legacy test proved less than its name (only the request body); the Playwright test asserts the saved result too. |

## Legacy data

`fixtures.ts` keeps `user.json`, `settings.json` and the typed name verbatim (`legacyUser`, `legacySettings`,
`legacyProfileUpdate`). Values that cannot hold on the real app are kept as `Legacy<Field>` next to the
corrected field:

- `LegacyId` `user-123` → `Id`: the UUID returned by real registration.
- `LegacyEmail` `alex.morgan@example.test` → `Email`: unique `cypress-settings-<uuid>@example.com` per test,
  because each test registers a fresh user.
- `LegacyTheme` `light` → `Theme` `system`: `GET /api/v1/settings` for a new user returns
  `{"notificationEmail":true,"notificationInApp":true,"notificationDesktop":false,"theme":"system","language":"en"}`.
  Neither test asserts the theme (the Settings page does not show it). The other settings values match.

## Run

```bash
cd frontend/client-app
npm run test:e2e:migrated -- --grep @CY-settings-01
```
