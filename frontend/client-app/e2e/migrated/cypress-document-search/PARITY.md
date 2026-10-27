# cypress-document-search migration parity

Legacy source: `tests/legacy-suites/cypress/cypress/e2e/document-search.cy.js` (branch `qe/legacy-suites-fixture`),
supporting files `cypress.config.js`, `package.json`, `cypress/support/e2e.js` (`visitAsUser`),
`cypress/fixtures/user.json`, `cypress/fixtures/search-results.json`.
Legacy result is a fresh, unmodified run (`npx cypress run --spec cypress/e2e/document-search.cy.js`,
Cypress 13.17.0, 2026-10-27) against the current client app on Vite :3000. Playwright result is from the
real local stack (Compose postgres, redis, localstack, meilisearch, auth-service, document-service,
file-service, search-service, api-gateway; Vite :3000), run twice in a row with identical results.

| Legacy ID | Legacy name | Legacy source | What the legacy test did | Legacy result vs current app | Playwright test (file › title) | What the Playwright test does | Playwright result | Verdict | Decision and reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CY-document-search-01 | finds a document by title | `tests/legacy-suites/cypress/cypress/e2e/document-search.cy.js#finds a document by title` | Stubbed every `**/api/v1/**` call (`{data: [], total: 0}`), `/auth/profile` with `user.json` and `/api/v1/search*` with `search-results.json`; set a fake JWT (`sub: user-123`) in localStorage; visited `/search?q=quarterly`; `cy.wait("@search")`; asserted text "Quarterly Planning" visible and the input `placeholder="Search files, documents, and folders..."` has value `quarterly`. No backend involved. | Passed (1/1, 2.7 s). It proves only that the search page renders a canned response and pre-fills the query from the URL; it never proves a document is found by its title. | `e2e/migrated/cypress-document-search/cypress-document-search.spec.ts` › CY-document-search-01 finds a document by title | Fixture `FindDocumentByTitle` registers a fresh unique user (display name "Alex Morgan"), creates the document "Quarterly Planning" with content "Review quarterly objectives and dates." through the gateway, and polls the real `GET /api/v1/search?q=quarterly` until it returns exactly that document's id (async SNS→SQS→search-service→MeiliSearch indexing). Then visits `/search?q=quarterly` with the real tokens and asserts the result link "Quarterly Planning" in `main` is visible and points to `/documents/<real id>`, and that the page search textbox holds `quarterly`. | Passed (run 1: 1/1; run 2: 1/1) | match | Converted. The legacy data works unchanged against the real app (title and query are kept verbatim). Playwright asserts what the name promises: the real search finds the seeded document and the result links to it (href check proves it is the seeded document, not a stub). Legacy stub values that cannot hold against a real backend are kept as `LegacyUserId` "user-123", `LegacyEmail`, `LegacyDocumentId` "doc-101" next to the server-issued values; the legacy test never asserted them. `cy.wait("@search")` dropped (web-first assertions replace it). Legacy placeholder identity not ported: the page input has no label, so it is located as the `textbox` inside `main` (one-line accessibility-gap comment). |

## Run

Search needs `meilisearch` and `search-service` on top of the stack in [the migrated suite README](../README.md):

```bash
docker pull mirror.gcr.io/getmeili/meilisearch:v1.6 && docker tag mirror.gcr.io/getmeili/meilisearch:v1.6 getmeili/meilisearch:v1.6
docker compose -f docker-compose.infra.yml -f docker-compose.yml build search-service
docker compose -f docker-compose.infra.yml -f docker-compose.yml up -d --no-build meilisearch search-service
curl --fail --retry 30 --retry-all-errors --retry-delay 2 http://localhost:8087/health
cd frontend/client-app && npm run test:e2e:migrated -- --grep @CY-document-search-01
```
