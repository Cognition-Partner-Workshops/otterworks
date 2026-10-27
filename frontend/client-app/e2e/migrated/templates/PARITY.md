# Templates migration parity

Tosca results are recorded evidence from `tests/legacy-suites/tosca/ExecutionLists/ClientRegression.xml`
(entries for TC-TPL-001..003) and `ExecutionLogs/template-library-2024-08.xml`, not a fresh Tosca run.
That run (RUN-TEMPLATE-2024-08) has no screenshots and is six months older than the 2025-02 client regression.

Decision `d-templates`: retire. The client app has no Templates screen to drive, so a converted test
could only fail against the catch-all `NotFound` route. No spec file is added for this folder.

| TestCase ID | Tosca name | Playwright test (file › title) | Tosca result (RUN-TEMPLATE-2024-08, 2024-08-12) | Playwright result | Verdict | Decision and reason |
| --- | --- | --- | --- | --- | --- | --- |
| TC-TPL-001 | View the template collection | none | Passed (RUN-TEMPLATE-2024-08, 2024-08-12) | not converted | retired with reason | Targets a client page headed "Templates" with a "Project brief" card (`Modules/Templates.xml` MA-TEMPLATES-001/003). No such screen exists: see [Evidence](#evidence) E1-E4. |
| TC-TPL-002 | Filter templates by name | none | Passed (RUN-TEMPLATE-2024-08, 2024-08-12) | not converted | retired with reason | Targets a "Search templates..." input on the same page (MA-TEMPLATES-002). No screen or filter exists: E1-E4. Also note `TestCaseDesign/Templates.csv` row `TemplateFilter` has an empty `Query`, so the recorded pass typed nothing into the filter. |
| TC-TPL-003 | Create a document from a template | none | Passed (RUN-TEMPLATE-2024-08, 2024-08-12) | not converted | retired with reason | Targets a "Use template" button (MA-TEMPLATES-004). No client UI or client API call creates a document from a template: E1-E4. The backend endpoint still exists (E5), so API-level coverage is possible but is a separate decision, not a UI conversion. |

## Evidence

Pinned to `main` @ `8d82c24`, `qe/tosca-to-playwright` @ `530c5fe`, legacy export `qe/legacy-suites-fixture` @ `dc2c369`.

- **E1 No route.** `frontend/client-app/src/App.tsx` declares no `/templates` route on
  [main](https://github.com/Cognition-Partner-Workshops/otterworks/blob/8d82c241203fdc59ea3a74d4d576f2c0ba762f14/frontend/client-app/src/App.tsx#L47-L78) or
  [qe/tosca-to-playwright](https://github.com/Cognition-Partner-Workshops/otterworks/blob/530c5fe67f05e7856af790be029cfda0907f8ec9/frontend/client-app/src/App.tsx#L47-L78);
  `/templates` falls through to `<Route path="*" element={<NotFound />} />`.
- **E2 No page.** [`src/pages/`](https://github.com/Cognition-Partner-Workshops/otterworks/tree/8d82c241203fdc59ea3a74d4d576f2c0ba762f14/frontend/client-app/src/pages)
  has no templates page (same listing on both branches).
- **E3 No client API.** [`src/lib/api.ts`](https://github.com/Cognition-Partner-Workshops/otterworks/blob/8d82c241203fdc59ea3a74d4d576f2c0ba762f14/frontend/client-app/src/lib/api.ts)
  contains no occurrence of "template" (case-insensitive) on either branch.
- **E4 Never in git history.** The UI was not removed in this repository; it was never in it. Pickaxe searches over every
  ref (`git log --all -S'<string>' -- frontend`) for `Use template`, `Search templates`, `from-template`,
  `Project brief` and `TemplatesPage` return no commits, and no file matching `*pages/templates*` or
  `*emplates.tsx` was ever added or deleted. The repository starts at `2dd5864` (2026-04-17) and the client
  `App.tsx` at `a324a50` (2026-07-15), both after the 2024-08 Tosca run, so the removal predates this history.
- **E5 Backend still serves templates (not removed).** document-service mounts
  [`templates.router` at `/api/v1/templates`](https://github.com/Cognition-Partner-Workshops/otterworks/blob/8d82c241203fdc59ea3a74d4d576f2c0ba762f14/services/document-service/app/main.py#L73)
  ([GET/POST list/create](https://github.com/Cognition-Partner-Workshops/otterworks/blob/8d82c241203fdc59ea3a74d4d576f2c0ba762f14/services/document-service/app/api/templates.py)),
  [`POST /api/v1/documents/from-template/{template_id}`](https://github.com/Cognition-Partner-Workshops/otterworks/blob/8d82c241203fdc59ea3a74d4d576f2c0ba762f14/services/document-service/app/api/documents.py#L487-L507),
  and api-gateway [routes `/api/v1/templates`](https://github.com/Cognition-Partner-Workshops/otterworks/blob/8d82c241203fdc59ea3a74d4d576f2c0ba762f14/services/api-gateway/internal/config/config.go#L119)
  to it. Added in `22862ac` (2026-04-17) and never removed. Only the client screen is missing.
- **Tosca sources.**
  [TC-TPL-001](https://github.com/Cognition-Partner-Workshops/otterworks/blob/dc2c3694415d61a2a3c5320c25b0d8290c706b57/tests/legacy-suites/tosca/TestCases/Templates/TC-TPL-001.xml),
  [TC-TPL-002](https://github.com/Cognition-Partner-Workshops/otterworks/blob/dc2c3694415d61a2a3c5320c25b0d8290c706b57/tests/legacy-suites/tosca/TestCases/Templates/TC-TPL-002.xml),
  [TC-TPL-003](https://github.com/Cognition-Partner-Workshops/otterworks/blob/dc2c3694415d61a2a3c5320c25b0d8290c706b57/tests/legacy-suites/tosca/TestCases/Templates/TC-TPL-003.xml),
  [Modules/Templates.xml](https://github.com/Cognition-Partner-Workshops/otterworks/blob/dc2c3694415d61a2a3c5320c25b0d8290c706b57/tests/legacy-suites/tosca/Modules/Templates.xml),
  [TestCaseDesign/Templates.csv](https://github.com/Cognition-Partner-Workshops/otterworks/blob/dc2c3694415d61a2a3c5320c25b0d8290c706b57/tests/legacy-suites/tosca/TestCaseDesign/Templates.csv),
  [ExecutionLogs/template-library-2024-08.xml](https://github.com/Cognition-Partner-Workshops/otterworks/blob/dc2c3694415d61a2a3c5320c25b0d8290c706b57/tests/legacy-suites/tosca/ExecutionLogs/template-library-2024-08.xml),
  [ExecutionLists/ClientRegression.xml](https://github.com/Cognition-Partner-Workshops/otterworks/blob/dc2c3694415d61a2a3c5320c25b0d8290c706b57/tests/legacy-suites/tosca/ExecutionLists/ClientRegression.xml#L20-L22).
