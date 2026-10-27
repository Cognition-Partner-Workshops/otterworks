# Sharing parity

| TestCase ID | Tosca name | Playwright test (file › title) | Tosca result (run ID, date) | Playwright result | Verdict | Decision and reason |
| --- | --- | --- | --- | --- | --- | --- |
| TC-SHARE-001 | View a shared file | sharing.spec.ts › TC-SHARE-001 View a shared file | Passed (RUN-CLIENT-2025-02, 2025-02-18) | Passed twice against real local stack | match | CSV SharedFile values retained verbatim. A separate unique owner uploads Roadmap.pdf through the API and shares it with the fresh test user; the recipient API listing and accessible card link prove it is shared. sharing.png and MODULE-SHARE SharedFileLink show Roadmap.pdf. |
| TC-SHARE-002 | Open a shared file | sharing.spec.ts › TC-SHARE-002 Open a shared file | Passed (RUN-CLIENT-2025-02, 2025-02-18) | Passed twice against real local stack | match | CSV OpenSharedFile values retained verbatim. Drop STEP-02's 5000 ms Wait; STEP-03 uses the accessible Roadmap.pdf link, not the obsolete hashed class. shared.tsx supplies a Download menu handler, but FileCard's card Link navigates to /files/:id. Assert that exact seeded file-detail URL, Roadmap.pdf heading and Download button. The legacy final click and sharing.png did not prove opening; Playwright now verifies the outcome promised by the name. |
| TC-SHARE-003 | View starred documents | sharing.spec.ts › TC-SHARE-003 View starred documents | Passed (RUN-CLIENT-2025-02, 2025-02-18) | Passed twice against real local stack | match | CSV StarredDocument values retained verbatim. This is /starred, not /shared: MODULE-SHARE StarredHeading and MODULE-DOCS DocumentCard agree with starred.png. Reuse seedWorkspace's real API documents and fresh user, then star Quarterly Planning through its accessible Star button. starredApi in src/lib/api.ts stores stars in browser localStorage, with no HTTP star endpoint; use the real UI rather than inventing an API or mocking it. |

## Evidence and verification

- Read-only legacy evidence: origin/qe/legacy-suites-fixture, TestCases/Sharing/*.xml, Modules/Sharing.xml, Modules/Documents.xml, TestCaseDesign/Sharing.csv, ExecutionLogs/client-regression-2025-02.xml (lines 94–115), ExecutionLists/ClientRegression.xml (entries 14–16), and Screenshots/sharing.png and starred.png. The execution list matches the newest log for all three cases.
- Reference shape: origin/qe/tosca-playwright-documents, e2e/migrated/documents/ (read only).
- Real stack: Compose PostgreSQL, Redis, LocalStack, auth-service, document-service, file-service, api-gateway; Vite on :3000. No page.route mocks, app changes, fixed waits, retries or expected failures.
- npm run lint: exit 0, one pre-existing react-hooks/exhaustive-deps warning in src/pages/file-detail.tsx:84 (resolvedUsers). npx tsc --noEmit: exit 0, no output.
- Full available migrated suite, npm run test:e2e:migrated: 3 passed, 0 failed in each of two consecutive runs. The harness branch contains no other executable migrated folders. Single-case traceability check --grep @TC-SHARE-001: 1 passed.
- No wrong CSV values, app defects, retirements or Playwright disagreements found. No Tosca/corrected-field substitution was needed.
