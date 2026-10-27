---
name: playwright-migration
description: >
  Read the Tosca export, run the Selenium and Cypress suites, and record
  per-TestCase Playwright parity for the client app and admin dashboard.
---

# Playwright migration

Use this workflow to compare the current browser suites with their Playwright equivalents.

## Read the Tosca export

Start under `tests/legacy-suites/tosca/`.

1. Read `Modules/*.xml` to find the HTML controls and identification properties.
2. Read `TestCases/<Folder>/*.xml` for TestSteps and their module attributes.
3. Open the referenced `TestCaseDesign/*.csv` file and select the named instance.
4. Read `ExecutionLists/ClientRegression.xml` for the recorded result and log path.
5. Open the matching file in `ExecutionLogs/` for step results, durations, and screenshots.

The list and log files reference TestCase IDs. Each screenshot path is relative to its execution log.

## Run the browser suites

Start the client app from `frontend/client-app`:

```bash
npm run dev -- --host 127.0.0.1 --port 3000
```

Run Cypress from `tests/legacy-suites/cypress` after installing its package:

```bash
npm install --no-package-lock
npm run test:e2e
```

The Cypress base URL is `http://localhost:3000`.

Start the Angular admin dashboard from `frontend/admin-dashboard`:

```bash
npm run start
```

The admin app listens on port 4200 by default. Run the Selenium suite from `tests/legacy-suites/selenium`:

```bash
mvn test
```

Set `ADMIN_BASE_URL` when the admin app uses another address.

## Add Playwright tests

| App | Playwright test directory |
| --- | --- |
| Client app | `frontend/client-app/e2e/migrated/` |
| Admin dashboard | `frontend/admin-dashboard/e2e/migrated/` |

Add the source TestCase ID to each converted test.

## Record parity

Use one row for every legacy TestCase ID. Record the Playwright test name, both results, and one verdict:

| TestCase ID | Playwright test | legacy result | Playwright result | verdict |
| --- | --- | --- | --- | --- |
| TC-... | `path/to/test.spec.ts` | Passed or Failed | Passed or Failed | match / legacy wrong / Playwright wrong / retired with reason |

A migration is complete only after every legacy test has a verdict. Use `retired with reason` when a test no longer belongs in the suite, and record the reason in the same row.
