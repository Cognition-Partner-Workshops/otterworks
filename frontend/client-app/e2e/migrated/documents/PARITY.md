# Documents migration parity

Tosca results are recorded evidence from `tests/legacy-suites/tosca/ExecutionLists/ClientRegression.xml`
and `ExecutionLogs/client-regression-2025-02.xml`, not a fresh Tosca run.

| TestCase ID | Tosca name | Playwright test (`e2e/migrated/documents/documents.spec.ts` › title) | Tosca result (RUN-CLIENT-2025-02, 2025-02-18) | Playwright result | Verdict | Decision and reason |
| --- | --- | --- | --- | --- | --- | --- |
| TC-DOC-001 | View the document list | `e2e/migrated/documents/documents.spec.ts` › TC-DOC-001 View the document list | Passed | Passed | match | Retain heading and seeded document-card verification. |
| TC-DOC-002 | Open a document | `e2e/migrated/documents/documents.spec.ts` › TC-DOC-002 Open a document | Passed | Passed | match | Playwright now proves navigation with the seeded document URL and editor heading; Tosca's DocumentTitle locator targeted the list-card `<p>` and never proved navigation. |
| TC-DOC-003 | Verify the dashboard document count | `e2e/migrated/documents/documents.spec.ts` › TC-DOC-003 Verify the dashboard document count | Passed | Failed with Tosca data (expected 3, rendered 4); Passed with corrected data (4) | legacy wrong | Decision: retain CSV value as `ToscaExpectedDocumentCount: "3"`, derive `ExpectedDocumentCount` from seeded documents. `ExecutionLogs/Screenshots/dashboard.png` shows 4; `Modules/Dashboard.xml` MA-DASH-002 has InnerText "4"; real API total is 4. Tosca's recorded pass is false, not an app defect. Assertion unchanged. |
| TC-DOC-004 | Filter documents by title | `e2e/migrated/documents/documents.spec.ts` › TC-DOC-004 Filter documents by title | Passed | Passed | match | Retain CSV filter and title; also verify nonmatching seeded document cards disappear. |

## Run

See [the migrated suite README](../README.md) for reproducible local-stack setup,
mirror workarounds, test commands, and report locations.
