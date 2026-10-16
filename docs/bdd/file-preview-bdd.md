# Inline File Preview BDD Scenarios

## BDD-01: Open preview by clicking a file in the list
**Traces to:** AC-01   **Category:** FUNC

**Given** a signed-in user is on `/files` with an uploaded file **When** they click the file card **Then** `/files/:id` opens with the inline preview and no file is saved or downloaded.

### Testing Flow
1. Register a fresh user and upload `preview.txt` through `POST /api/v1/files/upload`.
2. Open `/files` and click the `preview.txt` card.
3. Verify the browser is on `/files/<id>`, inline text is visible, and no download event fired.

## BDD-02: Show a Preview menu item on file cards only
**Traces to:** AC-02   **Category:** FUNC

**Given** a file card on Files, Dashboard, Recent, Shared, or Starred **When** the user opens `⋯` and picks `Preview` **Then** the app goes to `/files/:id`, and the item is not shown for folders.

### Testing Flow
1. Visit `/files` and open `⋯` on a file card.
2. Choose `Preview` and verify `/files/<id>` and the preview panel.
3. Open `⋯` on a folder card and verify `Preview` is absent.

## BDD-03: Preview bytes inline without triggering a download
**Traces to:** AC-03   **Category:** FUNC

**Given** any file type **When** its preview is open **Then** bytes load only via inline elements or `fetch`; no `download` attribute or non-renderable navigation is used, and Download happens only when its button is clicked.

### Testing Flow
1. Open `/files/<id>` for an uploaded file.
2. Inspect the preview requests and inline media/document elements.
3. Verify no download event or download link occurs until `Download` is clicked.

## BDD-04: Render raster images fitted to the preview panel
**Traces to:** AC-04   **Category:** FUNC

**Given** a PNG, JPG, GIF, WebP, BMP, or AVIF file **When** the preview opens **Then** the image is shown fitted to the panel via `<img>`.

### Testing Flow
1. Upload `preview.png` and visit `/files/<id>`.
2. Verify the `img` element has `naturalWidth > 0` and stays within the panel.

## BDD-05: Render SVG only as an inert image
**Traces to:** AC-05   **Category:** FUNC

**Given** an `image/svg+xml` file **When** the preview opens **Then** it is shown only via `<img>` (scripts inert), never inlined or iframed.

### Testing Flow
1. Upload `preview.svg` and visit `/files/<id>`.
2. Verify the SVG is the `img` source and no inline `<svg>` or SVG iframe is rendered.

## BDD-06: Preview PDF in a titled iframe
**Traces to:** AC-06   **Category:** FUNC

**Given** an `application/pdf` file **When** the preview opens **Then** the PDF is shown in an iframe titled with the file name, plus an `Open in new tab` link.

### Testing Flow
1. Upload `preview.pdf` and visit `/files/<id>`.
2. Verify the iframe title is `preview.pdf`.
3. Verify `Open in new tab` opens with `target="_blank"` and `rel="noopener noreferrer"`.

## BDD-07: Show source text with line numbers
**Traces to:** AC-07   **Category:** FUNC

**Given** a text, code, JSON, XML, JavaScript, TypeScript, YAML, shell, HTML, or log file **When** the preview opens **Then** content is shown as line-numbered plain text from a `Range: bytes=0-499999` fetch (HTML is shown as source).

### Testing Flow
1. Upload `preview.py` and visit `/files/<id>`.
2. Verify source text and line numbers are visible and the content request has `Range: bytes=0-499999`.
3. Repeat with `preview.html` and verify markup is source text rather than active HTML.

## BDD-08: Truncate large text previews
**Traces to:** AC-08   **Category:** FUNC

**Given** a text file larger than 500,000 bytes **When** the preview opens **Then** the first 500,000 bytes are shown with `Showing first 500 KB`, and the response is 206.

### Testing Flow
1. Generate and upload a 680 KB log file.
2. Visit `/files/<id>` and verify `Showing first 500 KB`.
3. Verify the content response is 206 with `Content-Range` and no more than 500,000 bytes are displayed.

## BDD-09: Render Markdown with a source toggle
**Traces to:** AC-09   **Category:** FUNC

**Given** a `.md` or `text/markdown` file **When** the preview opens **Then** formatted Markdown and a `Rendered`/`Source` toggle are shown; Source is line-numbered text and the 500 KB cap applies.

### Testing Flow
1. Upload `preview.md` and visit `/files/<id>`.
2. Verify the formatted heading and `Rendered` button.
3. Choose `Source`; verify line-numbered Markdown and `?view=source`.

## BDD-10: Render CSV and TSV as tables
**Traces to:** AC-10   **Category:** FUNC

**Given** a `.csv`/`.tsv` or CSV/TSV MIME file **When** the preview opens **Then** a table uses the first row as header, auto-detects the delimiter, and renders at most 1,000 data rows with `Showing first 1,000 of N rows` when more rows were parsed; the 500 KB cap applies and a partial final row is dropped.

### Testing Flow
1. Upload `preview.csv` and verify the first row is table headers.
2. Upload `preview.tsv` and verify tab-separated columns are recognized.
3. Upload a CSV with 1,500 data rows; verify 1,000 body rows and `Showing first 1,000 of 1,500 rows`.
4. For a truncated CSV, verify `Showing first 500 KB` and no incomplete final row; if both limits apply, verify both notices.

## BDD-11: Preview audio with native controls
**Traces to:** AC-11   **Category:** FUNC

**Given** an `audio/*` file **When** the preview opens **Then** a native `<audio controls preload="metadata">` player is shown.

### Testing Flow
1. Upload `preview.wav` and visit `/files/<id>`.
2. Verify the audio element has controls, a source, and `readyState >= 1`.

## BDD-12: Keep native video preview
**Traces to:** AC-12   **Category:** FUNC

**Given** a `video/*` file **When** the preview opens **Then** a native `<video controls>` player is shown.

### Testing Flow
1. Upload `preview.webm` and visit `/files/<id>`.
2. Verify a video element with controls and the presigned source is present.

## BDD-13: List ZIP archive entries without extraction
**Traces to:** AC-13   **Category:** FUNC

**Given** a `.zip` or ZIP MIME file **When** the preview opens **Then** entries list path, uncompressed size, and folder marker, with at most 1,000 rows and `Showing 1,000 of N`; nothing is extracted or opened.

### Testing Flow
1. Upload `preview.zip` and visit `/files/<id>`.
2. Verify entry names and uncompressed sizes appear.
3. Inspect requests to confirm Range GETs retrieve the central directory and no entry bytes are extracted.

## BDD-14: Convert and sanitize DOCX
**Traces to:** AC-14   **Category:** FUNC

**Given** a DOCX file **When** the preview opens **Then** the document is shown as HTML converted by Mammoth and cleaned by DOMPurify, including headings, lists, tables, and embedded images.

### Testing Flow
1. Upload `preview.docx` and visit `/files/<id>`.
2. Verify its document heading and content render in the panel.
3. Verify converted HTML has no active script or event-handler attributes.

## BDD-15: Preview XLSX sheets with a 1,000-row cap
**Traces to:** AC-15   **Category:** FUNC

**Given** an XLSX file **When** the preview opens **Then** a read-only table shows the active sheet with sheet tabs, at most 1,000 rows, and a notice when truncated.

### Testing Flow
1. Upload a two-sheet `preview.xlsx` and visit `/files/<id>`.
2. Verify sheet tabs and the first sheet table.
3. Select the second sheet and verify its cells and row cap.

## BDD-16: Show a Download fallback for unsupported formats
**Traces to:** AC-16   **Category:** FUNC

**Given** a PPTX, legacy DOC/XLS/PPT, binary, non-ZIP archive, or unknown type **When** the preview opens **Then** a fallback card shows a type icon, name, size, MIME type, `Preview isn't available for this file type`, and a `Download` button.

### Testing Flow
1. Upload `preview.bin` with `application/octet-stream`.
2. Visit `/files/<id>` and verify the name, type, size, fallback message, and `Download`.
3. Click `Download` and verify the existing download handler is invoked.

## BDD-17: Fall back to the extension for generic MIME types
**Traces to:** AC-17   **Category:** FUNC

**Given** an empty or `application/octet-stream` MIME type with a known extension such as `.md`, `.log`, `.yaml`, `.ts`, `.docx`, or `.zip` **When** the preview opens **Then** the extension determines the preview kind; no known extension shows the fallback card.

### Testing Flow
1. Upload `notes.md` as `application/octet-stream` and verify Markdown preview.
2. Upload a `README` file as `application/octet-stream` and verify the unsupported fallback.

## BDD-18: Give every stored MIME type a defined outcome
**Traces to:** AC-18   **Category:** FUNC

**Given** every MIME/extension seen in `otterworks-file-metadata` **When** each is opened **Then** it shows a renderer or fallback card, never a blank, crash, or download.

### Testing Flow
1. Exercise fixtures for image, SVG, PDF, text, CSV, Markdown, Python, log, HTML, JSON, and octet-stream.
2. Verify each file detail route shows a renderer or `Preview isn't available for this file type`.
3. Verify no test causes a download event or uncaught page error.

## BDD-19: Enable CORS for the LocalStack files bucket
**Traces to:** AC-19   **Category:** FUNC

**Given** a fresh LocalStack initialized by `scripts/localstack-init.sh` **When** the browser at `http://localhost:3000` sends a Range GET to a presigned URL **Then** preflight succeeds, the response has `Access-Control-Allow-Origin`, and `Content-Range` is exposed.

### Testing Flow
1. Initialize LocalStack and inspect `otterworks-files` with `aws s3api get-bucket-cors`.
2. Send `OPTIONS` to a presigned file URL with Origin `http://localhost:3000` and requested header `range`.
3. Verify HTTP 200 and the expected ACAO and exposed response headers.

## BDD-20: Configure deployed files-bucket CORS in Terraform
**Traces to:** AC-20   **Category:** FUNC

**Given** the Terraform storage module **When** `terraform validate` or `plan` runs **Then** it adds only `aws_s3_bucket_cors_configuration.files` with the agreed origins, methods, and headers.

### Testing Flow
1. Run `terraform fmt -check` and `terraform validate` in the storage module.
2. Review the plan to confirm the files-bucket CORS resource has only the approved rule.

## BDD-21: Show a stable loading state
**Traces to:** AC-21   **Category:** UI

**Given** a slow metadata, URL, or content load **When** the preview is waiting **Then** a spinner or skeleton appears in the preview panel per stage without a layout jump.

### Testing Flow
1. Open `/files/<id>` with a delayed metadata or preview response.
2. Verify a status spinner appears inside the existing preview panel.
3. Release the response and verify the panel is replaced without shifting the page layout.

## BDD-22: Keep the preview layout responsive
**Traces to:** AC-22   **Category:** UI

**Given** desktop and narrow (at most 768 px) viewports **When** any preview is shown **Then** the preview panel and metadata sidebar remain, wide content scrolls inside its panel, and the page has no horizontal overflow.

### Testing Flow
1. Open a long table at 1280 px wide and verify panel/sidebar layout.
2. Resize to 390 px and verify `document.documentElement.scrollWidth` does not exceed the viewport.
3. Capture the narrow viewport with the file details sidebar and preview visible.

## BDD-23: Require explicit approval before loading a large gated file
**Traces to:** AC-23   **Category:** UI

**Given** an image, PDF, video, audio, DOCX, or XLSX file larger than 104,857,600 bytes **When** its preview opens **Then** `Large file (N MB)` and `Load preview` appear with no bytes fetched until clicked, after which the normal renderer loads.

### Testing Flow
1. Start file-service locally with `MAX_UPLOAD_BYTES=209715200` and upload a real 101 MB image through the gateway API.
2. Open `/files/<id>` and verify `Large file (N MB)` and `Load preview`.
3. Verify no S3 request before clicking `Load preview`; click it and verify the image renderer loads.

## BDD-24: Show an empty-file state without fetching content
**Traces to:** AC-24   **Category:** UI

**Given** a file with `size = 0` **When** the preview opens **Then** `This file is empty` is shown and no content fetch occurs.

### Testing Flow
1. Unit-test `FilePreview` with real file metadata where `size` is `0`.
2. Verify `This file is empty` and that no download URL or S3 request is made.
3. The browser upload flow cannot create this state because file-service rejects zero-byte uploads; keep the service unchanged.

## BDD-25: Preserve list navigation history
**Traces to:** AC-25   **Category:** NAV

**Given** the user is in folder X at `/files?folder=X` or on Recent, Shared, Starred, or Dashboard **When** they open a preview and press browser Back then Forward **Then** Back restores that list/folder and view mode and Forward reopens the same preview.

### Testing Flow
1. Open `/files?folder=<folder-id>` in a chosen list/grid view.
2. Click a file card to open `/files/<id>`.
3. Use browser Back and Forward and verify the folder and preview are restored.

## BDD-26: Restore preview sub-state from URL parameters
**Traces to:** AC-26   **Category:** NAV

**Given** a Markdown file in Source view or an XLSX file on sheet 2 **When** the user reloads, uses Back/Forward, or opens the URL in a new tab **Then** `?view=source` or `?sheet=<name>` restores the same sub-state.

### Testing Flow
1. Choose `Source` on a Markdown preview and verify `?view=source`.
2. Reload `/files/<id>?view=source` and verify source remains selected.
3. Select the second XLSX sheet and repeat with the `sheet` parameter.

## BDD-27: Drop stale file content during navigation
**Traces to:** AC-27   **Category:** NAV

**Given** preview A is open **When** the user navigates to preview B **Then** only B content is shown and A content and requests are dropped.

### Testing Flow
1. Delay the content response for file A and open `/files/<id-A>`.
2. Navigate to `/files/<id-B>` before A finishes.
3. Verify B content appears and no stale A content remains in the preview panel.

## BDD-28: Refresh an expired preview URL once without prompting
**Traces to:** AC-28   **Category:** ERR

**Given** an expired or stale cached preview URL **When** an element errors, a fetch returns 403, or `Load preview` is clicked **Then** the URL is refetched and the load retried once without a prompt; media resumes at its current time.

### Testing Flow
1. Open an image preview and route its first presigned S3 request to return 403.
2. Verify a second `/api/v1/files/<id>/download` request occurs and the image renders.
3. Repeat with media after seeking; verify current time is restored after retry.

## BDD-29: Show retry and download on content failure
**Traces to:** AC-29   **Category:** ERR

**Given** storage is unreachable, CORS fails, a ZIP/DOCX/XLSX is corrupt, or parsing fails **When** the renderer fails after the AC-28 retry **Then** `Could not load preview`, `Retry`, and `Download` appear and the page remains usable.

### Testing Flow
1. Upload `corrupt.docx` and open `/files/<id>`.
2. Verify `Could not load preview`, `Retry`, and `Download`.
3. Click `Retry` and verify the preview error can be retried without losing the page.

## BDD-30: Handle a missing or deleted file
**Traces to:** AC-30   **Category:** ERR

**Given** the file ID does not exist or was deleted while open **When** metadata or URL lookup returns 404 **Then** `File not found` or `This file is no longer available` is shown without a retry loop.

### Testing Flow
1. Open an uploaded file and delete/trash it through the file API.
2. Reload `/files/<id>`.
3. Verify the not-found state and that no repeated URL requests occur.

## BDD-31: Keep active content inert
**Traces to:** AC-31   **Category:** ERR

**Given** HTML, SVG, Markdown containing raw HTML/scripts/images, or DOCX active content **When** previewed **Then** HTML is source text, SVG uses only `<img>`, Markdown raw HTML is dropped and Markdown image syntax displays alt text without an `<img>`, DOCX HTML is sanitized, and no script runs.

### Testing Flow
1. Open HTML and verify markup appears as source.
2. Open SVG and verify no inline SVG or iframe.
3. Open Markdown containing raw `<script>`/`<img>` and Markdown image syntax; verify no script or image element is created and only the Markdown image's alt text is visible.
4. Open an active-content DOCX and verify sanitized markup and no dialog.

## BDD-32: Redirect unauthenticated users to login
**Traces to:** AC-32   **Category:** RBAC

**Given** no valid session **When** the user opens `/files/:id` **Then** the API returns 401, the existing refresh flow redirects to `/login`, and no preview URL is issued.

### Testing Flow
1. Clear `otter_access_token` and `otter_refresh_token`.
2. Open `/files/<id>`.
3. Verify `/login`, a 401 metadata request, and no `/download` URL request.

## BDD-33: Keep preview behavior role-agnostic
**Traces to:** AC-33   **Category:** RBAC

**Given** signed-in users with USER, EDITOR, ADMIN, or OWNER roles **When** they open a file they can reach today **Then** the preview is the same for every role, with no new role gate and unchanged file-service access checks.

### Testing Flow
1. Open the same file detail route as a USER and ADMIN.
2. Verify the same preview renderer and controls appear.
3. Review the change set to verify no file-service authorization code changed.

## BDD-34: Load heavy renderer libraries lazily
**Traces to:** AC-34   **Category:** PERF

**Given** the production build **When** a user previews an image **Then** Markdown, CSV, ZIP, DOCX, and XLSX libraries are separate chunks fetched only for their type and main-bundle growth is at most 10 KB gzip.

### Testing Flow
1. Build the frontend and inspect Vite's chunk report and gzip sizes.
2. Open an image preview and verify heavy renderer chunks are not requested.
3. Open each heavy file type and verify its corresponding lazy chunk is requested.

## BDD-35: Bound preview transfer and render time
**Traces to:** AC-35   **Category:** PERF

**Given** a 680–690 KB log, an approximately 650 KB CSV, and a large ZIP **When** they are previewed **Then** the log and CSV show visible content in under 3 seconds, text/Markdown/CSV fetch at most 500,000 bytes, and ZIP listing reads only the central directory via Range, not the full file.

### Testing Flow
1. Navigate to the 680–690 KB log and measure until its line-numbered content is visible; assert under 3 seconds and a 206 Range response for `bytes=0-499999`.
2. Navigate to an approximately 650 KB CSV and measure until the table content is visible; assert under 3 seconds and at most 1,000 rendered data rows.
3. Open a large ZIP and inspect requests for Range GETs to the archive end.
4. Verify response sizes are far below the full archive size and no HEAD request is sent.

## AC → BDD Traceability Matrix

| AC-ID | Category | AC Title | BDD Scenario(s) | Status |
|---|---|---|---|---|
| AC-01 | FUNC | Open preview by clicking a file in the list | BDD-01 | Mapped |
| AC-02 | FUNC | "Preview" item in the file card ⋯ menu | BDD-02 | Mapped |
| AC-03 | FUNC | Preview never triggers a download | BDD-03 | Mapped |
| AC-04 | FUNC | Raster image preview | BDD-04 | Mapped |
| AC-05 | FUNC | SVG preview is inert | BDD-05 | Mapped |
| AC-06 | FUNC | PDF preview | BDD-06 | Mapped |
| AC-07 | FUNC | Text/code preview | BDD-07 | Mapped |
| AC-08 | FUNC | Large text is truncated | BDD-08 | Mapped |
| AC-09 | FUNC | Markdown preview | BDD-09 | Mapped |
| AC-10 | FUNC | CSV/TSV preview | BDD-10 | Mapped |
| AC-11 | FUNC | Audio preview | BDD-11 | Mapped |
| AC-12 | FUNC | Video preview kept | BDD-12 | Mapped |
| AC-13 | FUNC | ZIP contents listing | BDD-13 | Mapped |
| AC-14 | FUNC | DOCX preview | BDD-14 | Mapped |
| AC-15 | FUNC | XLSX preview | BDD-15 | Mapped |
| AC-16 | FUNC | Fallback for unsupported types | BDD-16 | Mapped |
| AC-17 | FUNC | Extension fallback for generic MIME | BDD-17 | Mapped |
| AC-18 | FUNC | Every stored file has a defined outcome | BDD-18 | Mapped |
| AC-19 | FUNC | Local bucket CORS | BDD-19 | Mapped |
| AC-20 | FUNC | Deployed bucket CORS | BDD-20 | Mapped |
| AC-21 | UI | Loading state | BDD-21 | Mapped |
| AC-22 | UI | Layout and responsiveness | BDD-22 | Mapped |
| AC-23 | UI | Large-file gate (100 MB) | BDD-23 | Mapped |
| AC-24 | UI | Empty file | BDD-24 | Mapped |
| AC-25 | NAV | Back/forward between list and preview | BDD-25 | Mapped |
| AC-26 | NAV | Preview sub-state in the URL | BDD-26 | Mapped |
| AC-27 | NAV | No stale content between files | BDD-27 | Mapped |
| AC-28 | ERR | Silent refresh of expired preview URL | BDD-28 | Mapped |
| AC-29 | ERR | Content load or parse failure | BDD-29 | Mapped |
| AC-30 | ERR | Missing/deleted file | BDD-30 | Mapped |
| AC-31 | ERR | Active content never runs | BDD-31 | Mapped |
| AC-32 | RBAC | Unauthenticated access | BDD-32 | Mapped |
| AC-33 | RBAC | Role-agnostic preview, access behaviour unchanged | BDD-33 | Mapped |
| AC-34 | PERF | Lazy-loaded renderer libraries | BDD-34 | Mapped |
| AC-35 | PERF | Bounded byte transfer | BDD-35 | Mapped |

### Coverage Summary

Total AC 35 · FUNC 20 UI 4 NAV 3 ERR 4 RBAC 2 PERF 2 · Unmapped: NONE

### Data Dependencies

- **DynamoDB `otterworks-file-metadata`:** read-only attributes include `id` (partition key), `name`, `mime_type`, `size_bytes`, `owner_id`, `is_trashed`, and `s3_key`.
- **S3:** file bytes are stored in local bucket `otterworks-files` or deployed bucket `${project}-files-${env}`, keyed by `s3_key` (`files/{owner_id}/{file_id}`). The browser uses presigned GET URLs with Range support.
- **Metadata API:** `GET /api/v1/files/{id}` returns file metadata used by the detail route and preview-kind resolver.
- **Download URL API:** `GET /api/v1/files/{id}/download` returns the presigned S3 URL used by preview renderers.
- **Call path:** FileCard → `/files/:id` → metadata query → `FilePreview` → `resolvePreviewKind(mimeType, name)` → `usePreviewUrl` → `filesApi.getDownloadUrl` → `GET /api/v1/files/{id}/download` → S3 bytes.

### Resolutions

`file-service` defaults `MAX_UPLOAD_BYTES` to `104857600` bytes, which is the same 100 MB gate; with defaults, no stored file can exceed the gate. AC-23 is verified by running file-service locally with `MAX_UPLOAD_BYTES=209715200` (an environment override only, not committed) and uploading a real approximately 101 MB file through the gateway API. The preview gate still applies to deployments configured with a higher upload limit.

The unchanged file-service rejects zero-byte uploads with HTTP 400 (`services/file-service/src/handlers.rs`), so AC-24 is covered by a component test that supplies zero-size metadata; its API-backed browser scenario is skipped rather than changing the service.
