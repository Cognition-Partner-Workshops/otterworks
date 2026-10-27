# Search migration parity

Tosca results are recorded evidence from `tests/legacy-suites/tosca/ExecutionLists/ClientRegression.xml`
and `ExecutionLogs/client-regression-2025-02.xml`, not a fresh Tosca run.

| TestCase ID | Tosca name | Playwright test (file › title) | Tosca result (RUN-CLIENT-2025-02, 2025-02-18) | Playwright result | Verdict | Decision and reason |
| --- | --- | --- | --- | --- | --- | --- |
| TC-SRCH-001 | Find a document by title | `e2e/migrated/search/search.spec.ts` › TC-SRCH-001 Find a document by title | Passed | Passed in faithful run and both final Search runs | match | Keep the CSV query and result; Playwright also proves the link targets the seeded document ID and the count is `1 result for “quarterly”`, as shown in `Screenshots/search.png`. Module MA-SEARCH-003's `/documents/doc-101` is an environment-specific ID, replaced with the seeded ID. |
| TC-SRCH-002 | Filter search results by type | `e2e/migrated/search/search.spec.ts` › TC-SRCH-002 Filter search results by type | Passed | Passed in faithful run without applying Type; passed in both final Search runs with the CSV Type filter | match | Tosca TestSteps never used the CSV `Type` column, so its pass did not prove filtering; the log's screenshot shows the same “quarterly” query. Playwright applies `document` through the Documents filter and proves the seeded `Release Notes.txt` file is excluded. |
| TC-SRCH-003 | Show an empty search result | `e2e/migrated/search/search.spec.ts` › TC-SRCH-003 Show an empty search result | Passed | Failed with Tosca data (`"0 results"` link not found; 10-second visibility timeout); passed in both final Search runs with the UI empty-state assertion | legacy wrong | Keep `ToscaResultText: "0 results"` as recorded data, but assert the actual `No results found` empty state. `src/pages/search.tsx` renders that EmptyState for an empty result set, no `"0 results"` text exists in client-app `src`, and the API total is 0. The log's `Screenshots/search.png` shows the “quarterly” query, not this case; the Tosca pass is false, not an app defect. |

## Run

See [the migrated suite README](../README.md) for reproducible local-stack setup,
mirror workarounds, test commands, and report locations.
