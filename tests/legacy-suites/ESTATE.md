# Legacy test estate

The repository contains three suites for the client app and admin dashboard. The export files retain their source format so a migration can compare each case with its Playwright counterpart.

## Tosca workspace

`tosca/` contains a readable workspace export for the client app.

| Folder | TestCase IDs | Client app screen |
| --- | --- | --- |
| Authentication | TC-AUTH-001, TC-AUTH-002, TC-AUTH-003, TC-AUTH-004 | Sign in and registration |
| Documents | TC-DOC-001, TC-DOC-002, TC-DOC-003, TC-DOC-004 | Dashboard and documents |
| Search | TC-SRCH-001, TC-SRCH-002, TC-SRCH-003 | Search |
| Sharing | TC-SHARE-001, TC-SHARE-002, TC-SHARE-003 | Shared and starred items |
| Settings | TC-SET-001, TC-SET-002, TC-SET-003 | Profile and preferences |
| Templates | TC-TPL-001, TC-TPL-002, TC-TPL-003 | Template collection |

`Modules/` stores HTML controls and their technical identification properties. Each file under `TestCases/<Folder>/` contains one TestCase ID and its TestSteps. A TestCaseDesign reference names the CSV sheet and data instance used by the steps. `ExecutionLists/ClientRegression.xml` records the result, duration, start time, and log reference for each case. The logs under `ExecutionLogs/` record each step; screenshot paths point to the PNG files in `ExecutionLogs/Screenshots/`.

## Selenium suite

`selenium/` contains the Java 17, Maven, TestNG suite for the Angular admin dashboard.

| Page object | Screen |
| --- | --- |
| `LoginPage` | Login |
| `UsersPage` | Users |
| `AuditPage` | Audit logs |
| `FeaturesPage` | Feature flags |
| `HealthPage` | System health |

The tests are grouped by screen:

| Test class | Test methods |
| --- | --- |
| `LoginTest` | `loginFormShowsEmailField`, `emptyCredentialsShowValidationMessage`, `passwordVisibilityCanBeChanged` |
| `UsersTest` | `userListShowsHeading`, `userSearchAcceptsText`, `roleFilterIsAvailable` |
| `AuditTest` | `auditPageShowsHeading`, `auditSearchAcceptsText`, `actionFilterIsAvailable` |
| `FeaturesTest` | `featurePageShowsHeading`, `featureSearchCanBeApplied`, `featureToggleCanBeSelected` |
| `HealthTest` | `healthPageShowsHeading`, `healthSummaryIsDisplayed`, `healthDataCanBeRefreshed` |

## Cypress suite

`cypress/` contains four client app specs:

| Spec | Flow |
| --- | --- |
| `sign-in.cy.js` | Sign in and required-field validation |
| `document-search.cy.js` | Search for a document |
| `settings.cy.js` | Update profile settings |
| `starred.cy.js` | Open a starred document |

The sign-in and document-search flows also appear in the Tosca suite.

## Local app screens

The Tosca and Cypress cases use the React client app at `frontend/client-app`. Its screens include authentication, dashboard, documents, search, shared items, starred items, settings, and the template collection. The Selenium suite uses the Angular admin dashboard at `frontend/admin-dashboard`; its cases cover login, users, audit logs, feature flags, and system health.
