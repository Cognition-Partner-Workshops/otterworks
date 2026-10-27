# Tosca baseline: Client App Regression

The single reference every Tosca-to-Playwright conversion of the client app, and the final
suite-wide parity report, is judged against. It restates the legacy export under
`tests/legacy-suites/tosca/` (read-only evidence, from `qe/legacy-suites-fixture`) and adds
no verdicts of its own.

- Execution list: `ExecutionLists/ClientRegression.xml` (`EL-CLIENT-001`, 20 `ExecutionEntry` elements).
- Logs: `ExecutionLogs/client-regression-2025-02.xml` (`RUN-CLIENT-2025-02`, 2025-02-18, 17 `Execution` elements)
  and `ExecutionLogs/template-library-2024-08.xml` (`RUN-TEMPLATE-2024-08`, 2024-08-12, 3 `Execution` elements).
  Each TestCase appears in exactly one log, so that log is its newest result.
- `Entry` / `Execution` give the line of the `ExecutionEntry` in `ClientRegression.xml` and of the
  `Execution` element in the log, at the export as committed on `qe/tosca-to-playwright`.
- Screenshots are `ExecutionLogs/Screenshots/<file>` from the `Execution`'s `<Screenshot>`;
  the Templates run records none.

## Baseline (Tosca ID order)

| TestCase ID | Folder | Tosca name | TestCaseDesign instance | Newest Tosca result (run ID, date) | Entry | Execution | Log screenshot | Owning plan / board |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| TC-AUTH-001 | Authentication | Sign in with a valid account | Authentication / ValidSignIn | Passed (RUN-CLIENT-2025-02, 2025-02-18) | ClientRegression.xml:3 | client-regression-2025-02.xml:3 | sign-in.png | In flight, outside this board |
| TC-AUTH-002 | Authentication | Validate an email address | Authentication / InvalidEmail | Passed (RUN-CLIENT-2025-02, 2025-02-18) | ClientRegression.xml:4 | client-regression-2025-02.xml:12 | sign-in.png | In flight, outside this board |
| TC-AUTH-003 | Authentication | Validate required registration fields | Authentication / RequiredName | Passed (RUN-CLIENT-2025-02, 2025-02-18) | ClientRegression.xml:5 | client-regression-2025-02.xml:21 | register.png | In flight, outside this board |
| TC-AUTH-004 | Authentication | Validate matching registration passwords | Authentication / PasswordMismatch | Passed (RUN-CLIENT-2025-02, 2025-02-18) | ClientRegression.xml:6 | client-regression-2025-02.xml:31 | register.png | In flight, outside this board |
| TC-DOC-001 | Documents | View the document list | Documents / DocumentList | Passed (RUN-CLIENT-2025-02, 2025-02-18) | ClientRegression.xml:7 | client-regression-2025-02.xml:42 | documents.png | In flight: PR #2234 (`qe/tosca-playwright-documents`) |
| TC-DOC-002 | Documents | Open a document | Documents / OpenDocument | Passed (RUN-CLIENT-2025-02, 2025-02-18) | ClientRegression.xml:8 | client-regression-2025-02.xml:49 | documents.png | In flight: PR #2234 (`qe/tosca-playwright-documents`) |
| TC-DOC-003 | Documents | Verify the dashboard document count | Documents / DashboardCount | Passed (RUN-CLIENT-2025-02, 2025-02-18) | ClientRegression.xml:9 | client-regression-2025-02.xml:56 | dashboard.png | In flight: PR #2234 (`qe/tosca-playwright-documents`) |
| TC-DOC-004 | Documents | Filter documents by title | Documents / FilterDocument | Passed (RUN-CLIENT-2025-02, 2025-02-18) | ClientRegression.xml:10 | client-regression-2025-02.xml:64 | documents.png | In flight: PR #2234 (`qe/tosca-playwright-documents`) |
| TC-SRCH-001 | Search | Find a document by title | Search / TitleSearch | Passed (RUN-CLIENT-2025-02, 2025-02-18) | ClientRegression.xml:11 | client-regression-2025-02.xml:71 | search.png | In flight, outside this board |
| TC-SRCH-002 | Search | Filter search results by type | Search / DocumentType | Passed (RUN-CLIENT-2025-02, 2025-02-18) | ClientRegression.xml:12 | client-regression-2025-02.xml:78 | search.png | In flight, outside this board |
| TC-SRCH-003 | Search | Show an empty search result | Search / NoResults | Passed (RUN-CLIENT-2025-02, 2025-02-18) | ClientRegression.xml:13 | client-regression-2025-02.xml:86 | search.png | In flight, outside this board |
| TC-SHARE-001 | Sharing | View a shared file | Sharing / SharedFile | Passed (RUN-CLIENT-2025-02, 2025-02-18) | ClientRegression.xml:14 | client-regression-2025-02.xml:94 | sharing.png | Board "OtterWorks web: Tosca to Playwright": Convert the Sharing folder (UNT15-3, plan s2.2) |
| TC-SHARE-002 | Sharing | Open a shared file | Sharing / OpenSharedFile | Passed (RUN-CLIENT-2025-02, 2025-02-18) | ClientRegression.xml:15 | client-regression-2025-02.xml:101 | sharing.png | Board "OtterWorks web: Tosca to Playwright": Convert the Sharing folder (UNT15-3, plan s2.2) |
| TC-SHARE-003 | Sharing | View starred documents | Sharing / StarredDocument | Passed (RUN-CLIENT-2025-02, 2025-02-18) | ClientRegression.xml:16 | client-regression-2025-02.xml:109 | starred.png | Board "OtterWorks web: Tosca to Playwright": Convert the Sharing folder (UNT15-3, plan s2.2) |
| TC-SET-001 | Settings | View profile settings | Settings / Profile | Passed (RUN-CLIENT-2025-02, 2025-02-18) | ClientRegression.xml:17 | client-regression-2025-02.xml:116 | settings.png | Board "OtterWorks web: Tosca to Playwright": Convert the Settings folder (UNT15-2, plan s2.1) |
| TC-SET-002 | Settings | Update email notification preference | Settings / Notifications | Passed (RUN-CLIENT-2025-02, 2025-02-18) | ClientRegression.xml:18 | client-regression-2025-02.xml:124 | settings.png | Board "OtterWorks web: Tosca to Playwright": Convert the Settings folder (UNT15-2, plan s2.1) |
| TC-SET-003 | Settings | Save profile details | Settings / SaveProfile | Passed (RUN-CLIENT-2025-02, 2025-02-18) | ClientRegression.xml:19 | client-regression-2025-02.xml:132 | settings.png | Board "OtterWorks web: Tosca to Playwright": Convert the Settings folder (UNT15-2, plan s2.1) |
| TC-TPL-001 | Templates | View the template collection | Templates / TemplateCollection | Passed (RUN-TEMPLATE-2024-08, 2024-08-12) | ClientRegression.xml:20 | template-library-2024-08.xml:3 | none recorded | Board "OtterWorks web: Tosca to Playwright": Retire the Templates cases with evidence (UNT15-4, plan s3.1) |
| TC-TPL-002 | Templates | Filter templates by name | Templates / TemplateFilter | Passed (RUN-TEMPLATE-2024-08, 2024-08-12) | ClientRegression.xml:21 | template-library-2024-08.xml:9 | none recorded | Board "OtterWorks web: Tosca to Playwright": Retire the Templates cases with evidence (UNT15-4, plan s3.1) |
| TC-TPL-003 | Templates | Create a document from a template | Templates / CreateFromTemplate | Passed (RUN-TEMPLATE-2024-08, 2024-08-12) | ClientRegression.xml:22 | template-library-2024-08.xml:15 | none recorded | Board "OtterWorks web: Tosca to Playwright": Retire the Templates cases with evidence (UNT15-4, plan s3.1) |

All 20 entries in the execution list are `Passed`; the `ExecutionEntry` result, start time
and duration match the `Execution` element for every row. The Templates entries are carried
into the 2025-02 list from the older 2024-08 run, not re-executed with the rest.

## Observations for the conversion tickets

Hypotheses checked against the export and the client-app source on `qe/tosca-to-playwright`.
They are not verdicts; each owning ticket decides its own verdict from a live run.

1. **`Modules/Dashboard.xml` has no TestCases folder of its own.** Confirmed: there is no
   `TestCases/Dashboard/`. It is *not* used by TC-DOC-003 only: `MODULE-DASH` appears in
   TC-DOC-003 (STEP-01 `DashboardHeading`, STEP-02 `DocumentCount`, STEP-03 `DocumentsLabel`)
   and in TC-AUTH-001 STEP-04 (`DashboardHeading`, the post-sign-in check). Also for the
   Documents owner: `Documents.csv` `DashboardCount` expects `ExpectedDocumentCount` = 3, while
   the module's XScan `DocumentCount` InnerText is `4` and `dashboard.png` shows 4 Documents,
   yet the step passed.
2. **TC-SHARE-003 "View starred documents" sits in the Sharing folder but is a Starred-page
   test.** Confirmed: STEP-01 verifies `StarredHeading` ("Starred", kept in `MODULE-SHARE`),
   STEP-02 verifies `DocumentCard` from `MODULE-DOCS` with `Sharing.DocumentTitle` =
   "Quarterly Planning"; `starred.png` is the `/starred` page (`StarredPage`, route in
   `src/App.tsx`). Nothing in the case touches sharing; seeding needs a starred document, not
   a share.
3. **TC-SHARE-002 "Open a shared file".** Confirmed: STEP-02 is `Wait` `5000` `ms` (logged
   5004 ms) and STEP-03 clicks `OpenSharedItem`, whose only identification is
   `ClassName=shared-item__6a93f2`. That class does not occur anywhere under
   `frontend/client-app/` (`git grep shared-item`), and `sharing.png` shows a single
   `Roadmap.pdf` card. The case ends on the click with no Verify, so the Tosca pass never
   proved a file opened. Per the standard the Wait is dropped and the locator is rebuilt by
   role/name.
4. **TC-SET-002 "Update email notification preference".** Confirmed as observed: STEP-02 clicks
   `EmailNotifications`, STEP-03 verifies `Enabled` on the same attribute. `settings.png` (the
   one screenshot shared by TC-SET-001..003) shows Email notifications on, and the attribute's
   XScan `ClassName` includes `bg-otter-600`, which `src/pages/settings.tsx` `ToggleRow`
   applies only when `checked` (default `notificationEmail ?? true`). A click on an already-on
   toggle turns it off, and the toggle renders no "Enabled" text (unnamed `<button>`, no
   `aria-checked`), so the Tosca pass is suspect. The screenshot alone does not prove whether
   it was taken before or after the click.
