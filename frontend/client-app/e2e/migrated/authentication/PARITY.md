# Authentication migration parity

Tosca results are recorded evidence from `tests/legacy-suites/tosca/ExecutionLists/ClientRegression.xml`
and `ExecutionLogs/client-regression-2025-02.xml` (run `RUN-CLIENT-2025-02`, 2025-02-18), not a fresh Tosca run.
Both cited screenshots (`Screenshots/sign-in.png`, `Screenshots/register.png`) show empty forms with no
validation message, so they do not support either Tosca message assertion.

| TestCase ID | Tosca name | Playwright test (file › title) | Tosca result (run ID, date) | Playwright result | Verdict | Decision and reason |
| --- | --- | --- | --- | --- | --- | --- |
| TC-AUTH-001 | Sign in with a valid account | `e2e/migrated/authentication/authentication.spec.ts` › TC-AUTH-001 Sign in with a valid account | Passed (RUN-CLIENT-2025-02, 2025-02-18) | Passed | match | CSV account `alex.morgan@example.test` is a shared persistent user; kept as `ToscaEmail`, and the fixture registers a disposable `alex.morgan-<uuid>@example.test` with the CSV password through the real auth API. Asserts `/dashboard` URL and the Dashboard heading, which is what the name promises. |
| TC-AUTH-002 | Validate an email address | `e2e/migrated/authentication/authentication.spec.ts` › TC-AUTH-002 Validate an email address | Passed (RUN-CLIENT-2025-02, 2025-02-18) | Failed with Tosca value ("Please enter a valid email address" not found); Passed with corrected assertion | legacy wrong | Tosca's text exists nowhere in the client app. `src/pages/login.tsx` renders `type="email"` without `noValidate`, so Chrome's constraint validation blocks submit for `not-an-address` (observed `validity.typeMismatch = true`, URL stays `/login`, Zod's "Please enter a valid email" is never reached). The recorded pass is false. Test now asserts the field is rejected as a type mismatch and the user is not signed in; Tosca value kept as a `tosca-expected` annotation. The browser's localized bubble text is not asserted. |
| TC-AUTH-003 | Validate required registration fields | `e2e/migrated/authentication/authentication.spec.ts` › TC-AUTH-003 Validate required registration fields | Passed (RUN-CLIENT-2025-02, 2025-02-18) | Failed with Tosca value ("Name is required" not found); Passed with corrected message | legacy wrong | For an empty name the app shows "Name must be at least 2 characters" (`register.tsx` Zod `min(2)`; same text in `bdd/features/authentication.feature` and `e2e/auth.spec.ts`). "Name is required" never existed in `src/` history. The recorded pass is false, not an app defect. Asserts the app's message and that the form stays on `/register`; Tosca value kept as a `tosca-expected` annotation. |
| TC-AUTH-004 | Validate matching registration passwords | `e2e/migrated/authentication/authentication.spec.ts` › TC-AUTH-004 Validate matching registration passwords | Passed (RUN-CLIENT-2025-02, 2025-02-18) | Passed | match | CSV values verbatim; "Passwords do not match" is shown under Confirm password. Also asserts the form stays on `/register`. |

## Run

Uses the same stack as Documents (auth-service through the gateway; no extra backend). See
[the migrated suite README](../README.md). Run with `npm run test:e2e:migrated -- --grep @tosca-Authentication`.
