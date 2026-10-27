# Client App Regression: suite-wide Tosca parity

Roll-up of every TestCase in `tests/legacy-suites/tosca/ExecutionLists/ClientRegression.xml`
(`EL-CLIENT-001`, 20 entries) in Tosca ID order, from each folder's `PARITY.md` on
`qe/tosca-to-playwright` and checked against [`TOSCA-BASELINE.md`](TOSCA-BASELINE.md).
Tosca columns restate the baseline; Playwright results come from two consecutive full runs of
`npm run test:e2e:migrated` on a fresh checkout of `qe/tosca-to-playwright` @ `e699b6a`
against the real local stack ([runbook](README.md)), not from the folder commits.

## Summary

| Verdict | Count | TestCases |
| --- | --- | --- |
| match | 4 | TC-SET-001, TC-SHARE-001, TC-SHARE-002, TC-SHARE-003 |
| legacy wrong | 1 | TC-SET-002 |
| Playwright wrong | 0 | |
| app defect | 1 | TC-SET-003 (pending SDET confirmation whether planted) |
| retired with reason | 3 | TC-TPL-001, TC-TPL-002, TC-TPL-003 |
| pending (in flight) | 11 | TC-AUTH-001..004, TC-DOC-001..004, TC-SRCH-001..003 |
| **Total** | **20** | |

Playwright runs: two consecutive full runs on 2026-10-27, identical per-test outcomes: 6 tests each, 5 passed and 1 expected failure (TC-SET-003, `test.fail()`), 0 unexpected failures, 0 flaky, 0 skipped. Authentication, Documents and Search specs are not on the branch, so they did not run. `npm run lint`: exit 0 (one existing `react-hooks/exhaustive-deps` warning in `src/pages/file-detail.tsx:84`); `npx tsc --noEmit`: exit 0, no output.

**Legacy wrong**
- **TC-SET-002 Update email notification preference.** Email notifications default to ON
  (`notificationEmail ?? true` in `src/pages/settings.tsx`, DB default true; `settings.png` and
  the XScan `bg-otter-600` class show it on before the click), so Tosca's click turns it off and
  its post-click "Enabled" Verify was a false pass. Decision: keep the Tosca value as
  `ToscaExpected`, assert the corrected `Disabled`, verified through the real authenticated
  settings API before and after. See [settings/PARITY.md](settings/PARITY.md).

**App defect**
- **TC-SET-003 Save profile details.** The client sends `PATCH /api/v1/auth/profile`
  (`src/lib/api.ts:106`) but auth-service `AuthController` maps only `PUT /profile`, so save
  returns HTTP 500 (`HttpRequestMethodNotSupportedException`) and nothing persists. Decision: keep
  the correct success and persistence assertions and mark the test `test.fail()`; no app code
  change. Labelled an app defect **pending SDET confirmation** of whether it is a planted lab
  bug (AGENTS.md: planted bugs are not fixed in a conversion).

**Retired**
- **TC-TPL-001..003** (Templates, older run `RUN-TEMPLATE-2024-08`, no screenshots). The client
  app has no Templates screen, route, page or client API call, and git history never had one;
  no spec is added. See [templates/PARITY.md](templates/PARITY.md) E1-E4. The template API still
  exists in document-service (`/api/v1/templates`, `POST /api/v1/documents/from-template/{id}`,
  routed by the gateway, E5); API-level coverage is out of scope for this UI migration (plan
  decision `d-templates-api`).

**Pending (in flight)**
- Authentication (TC-AUTH-001..004) and Search (TC-SRCH-001..003) are converted outside this
  board; Documents (TC-DOC-001..004) is in open PR #2234 (`qe/tosca-playwright-documents`).
  None of their `PARITY.md` files is on `qe/tosca-to-playwright` yet, so their rows carry the
  baseline Tosca columns only. A later refresh fills them when they land.

## Parity table

| TestCase ID | Tosca name | Playwright test (file › title) | Tosca result (run ID, date) | Playwright result | Verdict | Decision and reason |
| --- | --- | --- | --- | --- | --- | --- |
| TC-AUTH-001 | Sign in with a valid account | not on branch | Passed (RUN-CLIENT-2025-02, 2025-02-18) | pending | pending (in flight) | Authentication folder converted outside this board; not on `qe/tosca-to-playwright` yet. |
| TC-AUTH-002 | Validate an email address | not on branch | Passed (RUN-CLIENT-2025-02, 2025-02-18) | pending | pending (in flight) | Authentication folder converted outside this board; not on `qe/tosca-to-playwright` yet. |
| TC-AUTH-003 | Validate required registration fields | not on branch | Passed (RUN-CLIENT-2025-02, 2025-02-18) | pending | pending (in flight) | Authentication folder converted outside this board; not on `qe/tosca-to-playwright` yet. |
| TC-AUTH-004 | Validate matching registration passwords | not on branch | Passed (RUN-CLIENT-2025-02, 2025-02-18) | pending | pending (in flight) | Authentication folder converted outside this board; not on `qe/tosca-to-playwright` yet. |
| TC-DOC-001 | View the document list | not on branch | Passed (RUN-CLIENT-2025-02, 2025-02-18) | pending | pending (in flight) | Documents folder in open PR #2234 (`qe/tosca-playwright-documents`). |
| TC-DOC-002 | Open a document | not on branch | Passed (RUN-CLIENT-2025-02, 2025-02-18) | pending | pending (in flight) | Documents folder in open PR #2234 (`qe/tosca-playwright-documents`). |
| TC-DOC-003 | Verify the dashboard document count | not on branch | Passed (RUN-CLIENT-2025-02, 2025-02-18) | pending | pending (in flight) | Documents folder in open PR #2234 (`qe/tosca-playwright-documents`). |
| TC-DOC-004 | Filter documents by title | not on branch | Passed (RUN-CLIENT-2025-02, 2025-02-18) | pending | pending (in flight) | Documents folder in open PR #2234 (`qe/tosca-playwright-documents`). |
| TC-SRCH-001 | Find a document by title | not on branch | Passed (RUN-CLIENT-2025-02, 2025-02-18) | pending | pending (in flight) | Search folder converted outside this board; not on `qe/tosca-to-playwright` yet. |
| TC-SRCH-002 | Filter search results by type | not on branch | Passed (RUN-CLIENT-2025-02, 2025-02-18) | pending | pending (in flight) | Search folder converted outside this board; not on `qe/tosca-to-playwright` yet. |
| TC-SRCH-003 | Show an empty search result | not on branch | Passed (RUN-CLIENT-2025-02, 2025-02-18) | pending | pending (in flight) | Search folder converted outside this board; not on `qe/tosca-to-playwright` yet. |
| TC-SHARE-001 | View a shared file | `sharing/sharing.spec.ts` › `TC-SHARE-001 View a shared file` | Passed (RUN-CLIENT-2025-02, 2025-02-18) | Passed in both runs (run 1, run 2; 2026-10-27) | match | CSV values verbatim; a separate owner uploads and shares `Roadmap.pdf` with the fresh user, proven by the recipient API listing and the accessible card link. See [sharing/PARITY.md](sharing/PARITY.md). |
| TC-SHARE-002 | Open a shared file | `sharing/sharing.spec.ts` › `TC-SHARE-002 Open a shared file` | Passed (RUN-CLIENT-2025-02, 2025-02-18) | Passed in both runs (run 1, run 2; 2026-10-27) | match | 5000 ms Wait dropped; obsolete hashed-class locator replaced by the accessible `Roadmap.pdf` link. Tosca ended on the click with no Verify; Playwright asserts the file-detail URL, heading and Download button. |
| TC-SHARE-003 | View starred documents | `sharing/sharing.spec.ts` › `TC-SHARE-003 View starred documents` | Passed (RUN-CLIENT-2025-02, 2025-02-18) | Passed in both runs (run 1, run 2; 2026-10-27) | match | A `/starred` test filed under Sharing. Stars are browser-local (`starredApi` in `src/lib/api.ts`, no HTTP endpoint), so the test stars `Quarterly Planning` through the real Star button. |
| TC-SET-001 | View profile settings | `settings/settings.spec.ts` › `TC-SET-001 View profile settings` | Passed (RUN-CLIENT-2025-02, 2025-02-18) | Passed in both runs (run 1, run 2; 2026-10-27) | match | Faithful run with the CSV email failed only because each test registers a fresh user; `ToscaEmail` keeps the CSV value and the corrected `Email` is the seeded user's address. See [settings/PARITY.md](settings/PARITY.md). |
| TC-SET-002 | Update email notification preference | `settings/settings.spec.ts` › `TC-SET-002 Update email notification preference` | Passed (RUN-CLIENT-2025-02, 2025-02-18) | Passed with corrected `Disabled` expectation in both runs (2026-10-27) | legacy wrong | Toggle defaults ON, so the click disables it; Tosca's post-click "Enabled" was a false pass. Corrected expectation `Disabled`, confirmed by the real settings API (true before, false after). |
| TC-SET-003 | Save profile details | `settings/settings.spec.ts` › `TC-SET-003 Save profile details` | Passed (RUN-CLIENT-2025-02, 2025-02-18) | Expected failure (`test.fail()`) in both runs (2026-10-27): STEP-02 `expect(profileResponse.ok()).toBe(true)` received `false` for the profile PATCH (`settings.spec.ts:80`) | app defect | Client `PATCH /auth/profile` vs `AuthController` PUT-only → HTTP 500, nothing persists. Kept as `test.fail()` with correct assertions; app code unchanged. Pending SDET confirmation whether this is a planted lab bug. |
| TC-TPL-001 | View the template collection | none | Passed (RUN-TEMPLATE-2024-08, 2024-08-12) | not converted | retired with reason | No Templates screen in the client app (no route, page or client API; never in git history). See [templates/PARITY.md](templates/PARITY.md) E1-E4. |
| TC-TPL-002 | Filter templates by name | none | Passed (RUN-TEMPLATE-2024-08, 2024-08-12) | not converted | retired with reason | Same as TC-TPL-001; the CSV `TemplateFilter` row also has an empty `Query`, so the recorded pass typed nothing. |
| TC-TPL-003 | Create a document from a template | none | Passed (RUN-TEMPLATE-2024-08, 2024-08-12) | not converted | retired with reason | No client UI creates a document from a template. The backend endpoint still exists (E5); API-level coverage is out of scope (`d-templates-api`). |

## Changes since the folder commits

None. Every executed row gave the same outcome as recorded in its folder `PARITY.md` (Settings at `038fc1e`/`e699b6a`, Sharing at `7d28d63`), so nothing is flagged back to a folder ticket.
