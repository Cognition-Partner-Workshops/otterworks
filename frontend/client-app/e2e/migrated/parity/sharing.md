# Parity: Tosca `TestCases/Sharing` → Playwright

Last Tosca execution: `tests/legacy-suites/tosca/ExecutionLists/ClientRegression.xml`
and `ExecutionLogs/client-regression-2025-02.xml`. Playwright uses local Vite and
service-contract route mocks, not live services.

| TestCase ID | Playwright test | Tosca result (last log) | Playwright result | Verdict | Decision and reason |
| --- | --- | --- | --- | --- | --- |
| TC-SHARE-001 | `e2e/migrated/sharing.spec.ts` › `TC-SHARE-001 View a shared file` (`@TC-SHARE-001`) | Passed | Passed | Match | Module MA-SHARE-001 InnerText and sharing.png both show "Shared with me"; MA-SHARE-002, the CSV and screenshot agree on "Roadmap.pdf". The current shared page renders that heading and FileCard link. |
| TC-SHARE-002 | `e2e/migrated/sharing.spec.ts` › `TC-SHARE-002 Open a shared file` (`@TC-SHARE-002`) | Passed | Passed | Match (Playwright checks more) | Tosca verifies only "Shared with me", waits 5000 ms (log: 5004 ms), then clicks an unnamed scanned class with no final Verify. Its sharing.png still shows the list, so the pass does not establish an opened file. Playwright replaces the wait with a visible Roadmap.pdf link, clicks it, and asserts `/files/:id` and the detail heading from CSV FileName. |
| TC-SHARE-003 | `e2e/migrated/sharing.spec.ts` › `TC-SHARE-003 View starred documents` (`@TC-SHARE-003`) | Passed | Passed | Match | MA-SHARE-004 InnerText, starred.png and current page agree on "Starred". Documents module/card, CSV and starred.png agree on "Quarterly Planning". Starred IDs are localStorage-backed in current starredApi, scoped by user; the page fetches `/documents/doc-101`, not a starred-list endpoint. |

## Contract and history cross-check

- `git log -S 'Shared with me' -- frontend/client-app/src/pages/shared.tsx`
  and `git log -S 'Starred' -- frontend/client-app/src/pages/starred.tsx` identify
  `a324a50d5`; its pages retain these headings. `git log -S 'Roadmap.pdf'` and
  `git log -S 'Quarterly Planning' -- frontend/client-app/src` return no matches:
  these values are data, not hard-coded application copy. Screenshot/module/CSV
  evidence supplies them; no stale verify value was found.
- `services/file-service/src/main.rs` routes GET `/files/shared` to
  `handlers::list_shared_files`. `metadata::list_shares_for_user` scans shares
  filtered by authenticated user; the handler deduplicates file IDs, ignores
  missing/trashed files, preserves scan order (no sort), then applies page >= 1,
  page_size default 50 capped at 100, returning `{files,total,page,page_size}`.
  The mock treats workspace.user as the gateway-authenticated user.
- `handlers::get_file_metadata` returns flattened FileMetadata plus `shared_with`;
  `download_file` returns `{url,expires_in_secs:3600}`. Invented UUIDs and S3 key
  are fixture-only. The download URL is synthetic; PDF rendering is not asserted.
- There is no starred-list service contract: `src/lib/api.ts` starredApi reads
  `otter_starred_items`; `pages/starred.tsx` requests each starred document by ID.
  Existing document detail mocking copies document-service's snake_case response.
  No fictitious starred endpoint was added. No app regression was observed.

Report screenshot is kept outside the repo at `/home/ubuntu/sharing-report.png`,
matching the Documents branch's policy (no tracked report screenshot).
