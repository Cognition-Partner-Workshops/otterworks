# report-service Java 8 replay corpus

This directory records the current Java 8 / Spring Boot 2.5.15 HTTP contract before
the Java 17 upgrade. It covers `/health`, `/health/archive`, an unmapped route, the
report CRUD and validation endpoints, CSV/Excel/PDF generation and downloads for
every `ReportCategory`, reconciliation JSON/CSV/HTML and `latest`, and archive
document/raw/hash/not-found routes. The output matrix uses a fixed UTC window that
crosses a Chicago date boundary, plus summer windows for CSV, Excel, and PDF. The
upstream stub also exercises the analytics `empty` and `upstream-error` responses.

## Run it

From this directory, `./run.sh image` builds the jar with the same Java 8 Maven
builder and the unmodified `../Dockerfile` runtime stage. This is the fallback
when a Docker build cannot reach Maven Central. Point Compose at that prebuilt
image for startup:

```sh
REPORT_IMAGE=report-service:parity ./run.sh up
./run.sh replay --context all --stage full --out ~/parity-evidence/replay
./run.sh down
```

Alternatively, `./run.sh up` builds the baseline image itself when
`REPORT_IMAGE` is unset. `./run.sh record --context all` records a reference from
the live baseline and regenerates `SHA256SUMS`. `./run.sh down` removes the stack
and its volumes. Replay does not reset state automatically: run `down` and `up`
before each replay that requires a fresh database. The default service URL is
`http://localhost:18091`. `PARITY_PORT` changes the host port, and
`COMPOSE_PROJECT_NAME` isolates a second local stack. This Compose stack is
local-only and does not deploy to a cluster.

Cases are ordered and stateful within `common`, `reports`, `outputs`,
`reconciliation`, and `archive`. Each full replay uses one fresh report database
and one fresh archive ledger fixture when started using the instructions above.
A case's `capture` maps a symbolic name to a
JSON response field; `{name}` substitutions are applied to later paths and bodies.
`waitFor` polls a captured report before a download until its status is `COMPLETED`
or `FAILED`. Captured IDs are normalized only at JSON keys named `id`, and in
report `downloadUrl` values.

## Normalization and comparison

JSON is canonicalized while preserving received key order, like the legacy-portal
harness. The harness records status,
complete `Content-Type`, normalized `Content-Disposition`, and body. Media types
compare by family for JSON (`application/json` and `application/*+json`); charset
parameters are compared separately and differences are reported. CSV/HTML/text
remain text. Excel files are represented as JSON with per-sheet rows (each cell's
string value and type letter), merged ranges, and auto-filter refs. PDF files are
represented as JSON with page count, page media boxes/rotations, and extracted
text lines. Parser dependencies are pinned in `requirements.txt`.

Volatile JSON fields are explicitly listed per case. A listed timestamp is
replaced only if it matches replay-time now within ten minutes and is rendered in
the recorded UTC format; a Chicago/other-offset rendering is marked
`<now:FORMAT:SERVER-TZ>`, and any other value is marked `<unrecognized:value>`.
Fixed request dates are never masked. Generated `MMM dd, yyyy HH:mm` display
stamps and `yyyyMMdd_HHmmss` attachment filename stamps receive the same UTC vs
server-time-zone check. For the defaulted-date case, period endpoints are checked
against the runtime's UTC now and UTC now minus 30 calendar days; they are not
blindly replaced. Its `window_from` and `window_to` CSV data columns are checked
the same way, without masking the fixed event timestamps. Reconciliation
`generated_at` is also time-dependent and is explicitly volatile on run JSON
cases.

The 202 create body returns the saved entity. `ReportService.createReport` saves
it as `PENDING`, then starts the worker from an after-commit callback; the worker
re-reads a separate entity and updates it asynchronously. Therefore the POST
response retains the saved `PENDING` state even when polling immediately observes
`COMPLETED`. Two baseline recordings confirm this state; `status`, completion
fields, and IDs are not silently masked.

The `upstream-error` stub response currently causes analytics report generation
to fail, so it is recorded as a separate `FAILED` status case. The complete
category × format output matrix uses successful upstream data and verifies every
download; the failed report has no downloadable artifact. The service source is
left unchanged.

## AA-06

`demos/app/complexity-manifest.json` defines AA-06 as the report-service parity
fault where a report column formats a date in the server time zone after upgrade.
The replay corpus deliberately preserves fixed-window Period text across the
Chicago boundary and verifies dynamic generated stamps as UTC or server-zone
values. A negative control that changes `ReportDateUtils.DISPLAY_FORMAT` to its
default time zone should diverge on those values; this is evidence that the replay
can detect the planted AA-06 behavior, not a request to change the golden source.
