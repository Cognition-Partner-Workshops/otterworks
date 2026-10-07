# The presenter guide for Devin as a partner engineer

This guide is for the person who opens the Partner Demo - ViewOnly organization in front of a partner or customer engineering audience and talks for twenty to forty minutes. Every item you show is a Devin session that the Pre-Sales Solution Architect persona started. You sign in through the Field Kit SSO page, pick the area and the identity, and that persona's sidebar is the demo. Nothing here needs a cloud account: every session worked on source code, a local Compose stack, the macOS Simulator, GitHub Actions or one of Devin's own surfaces.

## The one idea

Devin is an AI software engineer you delegate to, the way you delegate to a colleague on the team. You hand Devin a request in plain language, and Devin goes to the systems the work needs (the repository, the wiki, the running stack, the simulator, the scan results), does the work, proves the result and leaves the evidence where the team can audit it. The demo works when the audience recognizes work from their own week in each session and sees that the work finished without anyone hovering.

## The delegation tests

Before you open a session, say which of these the work passes. Most of the sessions pass several.

1. The judgment is easy and the volume is the hard part.
2. The same job comes back every week, every month, every alarm.
3. The job is tedious, and nobody on the team wants to be the one who does it.
4. A person cannot hold the context: logs, docs, deployment history, scan results, all from different systems.
5. A corpus, a gate, an alarm state or a clean-state check says done, so the agent keeps going until the check passes.
6. The job blocks someone more expensive, or has to run at three in the morning.

The on-demand worker shape runs through the whole portfolio. Something happens (an alert, a scan result, a bug report, a CVE advisory), a session starts from it, pulls what the job needs, does one bounded piece of work, checks the result and leaves an artifact. Say that sentence once, early, and point at the shape every time a session starts without a person.

## The eight families

| Family | What the audience worries about | Sessions |
|---|---|---|
| Application modernization | Getting logic out of stored procedures and old frameworks without breaking anything | Rating out of the billing procedures, the playbook and its two children, search-service on the Migrations board |
| Application development | A feature from a one-paragraph spec to a reviewed pull request | Make a copy of a document |
| Application maintenance | A CVE across several build files, a bug report nobody can reproduce | Text4Shell across the JVM modules as a workflow, the iOS base URL |
| Quality engineering | Untested modules, a red job everyone ignores, accessibility nobody measured | File-service coverage, the document-service test health, the public pages under axe |
| Digital engineering | A defect a user sees on screen, a native app in the simulator | Trash and Download on screen, the iOS safe area |
| Security vulnerability triage | Which findings are real | Eight findings in, three fixed with runtime proof |
| Code scans | Devin's own scan of the repository and a fix for what it found | The security scan, the search scoping fix |
| On-call | The page at three in the morning | The tester and the automation's responder |

## The sessions in presenting order

### 1. Rating out of the legacy billing procedures

Session: https://partner-workshops.devinenterprise.com/sessions/26f868033ffa479394bf4efc7113f646. PR: https://github.com/Cognition-Partner-Workshops/otterworks/pull/1831.

Say first: "Billing still runs in stored procedures nobody wants to open. We asked Devin to take one module out, prove the new code gives the same answers, and write down how to do the next one."

Tests: 3, 4 (the procedure source, the fixture database, the service code and the parity harness read together), 5 (the parity corpus is the contract).

What to open: the prompt, the rules ledger Devin wrote from the procedure source and the one question it asked before writing code, the parity run (`PASS=8 FAIL=0 SKIP=0`), the Devin Review on the PR with its three findings and Devin's replies, and the teardown of the local stack at the end. Say that Devin left the quirks it found tagged as follow-ups in the ledger instead of quietly fixing them.

### 1b. The playbook and its children

Playbook: `Extract one legacy billing module into billing-service with parity` (open it from the Playbooks page of the organization). Children: invoicing https://partner-workshops.devinenterprise.com/sessions/d545c14d3b0248bb90b26dbe94355015 and dunning https://partner-workshops.devinenterprise.com/sessions/bf51e4619882435abb653a541fccb712.

Say first: "The first module was the expensive one. The second and third cost one paragraph each."

Tests: 1, 2.

What to open: the playbook text, which is the method the parent wrote down; the two children, each with its own ledger, its own local stack and its own parity run; and the parent's summary when both reported back. Skip the ledger discussion in the children unless someone asks how Devin treats legacy behaviour it disagrees with (it keeps it and tags it).

### 1c. Search-service from Flask to FastAPI on the Migrations board

Board: https://partner-workshops.devinenterprise.com/org/partner-demo-viewonly/migrations. Parent session: https://partner-workshops.devinenterprise.com/sessions/f7c1e01a55ce4717bf6aa80f32c38021. PR: https://github.com/Cognition-Partner-Workshops/otterworks/pull/1845.

Say first: "A framework move is many small tickets in a fixed order. On the Migrations board Devin plans them, works them and shows progress."

Tests: 1, 2, 5 (the 130-case behaviour transcript and the test baseline are the gate for every later ticket).

What to open: the one sentence the persona typed on the Migrations page, the plan Devin drafted and the persona approved, the eleven tickets with their dependencies, the first worker's transcript (130 HTTP cases, zero diffs on replay against Flask, five runs) and the baseline worker's finding that two contract tests already fail on `main`. Then the end of the board: eleven tickets done by eleven small workers, the replay on FastAPI at 130 of 130 byte for byte, the Compose smoke test at 13 of 13, and the one PR against `main` with its Accepted differences list. The persona made two decisions, both in the product: keep Flask's HTML 400 page for parity (in chat), and accept the two server-level differences, the reason phrase and header casing, through the pick on the replay ticket in the Plan view.

### 2. Make a copy of a document

Session: https://partner-workshops.devinenterprise.com/sessions/0682a839d6a7404e8cf9fb67654c4b87. PR: https://github.com/Cognition-Partner-Workshops/otterworks/pull/1839.

Say first: "A product manager wrote one paragraph: users want to duplicate a document. Devin read the wiki first, then the team's conventions, then built it through to a reviewed pull request."

Tests: 3, 4 (the DeepWiki page for the repository, the repository knowledge, the document-service, the gateway and the web app), 5 (API tests, frontend tests and the browser run).

What to open: the DeepWiki read before any code change, the spec Devin wrote back, the new `POST /documents/{id}/copy` route and the card menu action, the API and frontend tests (16 client tests, 81 service tests passing), the four browser screenshots and the recording of `Copy created` on the real Compose stack, the Devin Review finding (three other card views showed a menu item that did nothing) and the commit that fixed it, the skill Devin offered to save for the browser check (it stayed an offer; the saved one is in act 5), and `docker compose down -v` at the end. The one decision the persona made: copying stays owner-only, because the service has no per-user sharing yet.

### 3. Text4Shell across the JVM modules, as a workflow

Session: https://partner-workshops.devinenterprise.com/sessions/d99e7d2407814d14bf664f12a7368228. PR: https://github.com/Cognition-Partner-Workshops/otterworks/pull/1836.

Say first: "One advisory, three build files, three JDKs. The judgment is small and the volume is the problem, so Devin ran it as a workflow with one child per module."

Tests: 1, 2, 5 (`deps-gate` and `deps-transcript` say done; exit code 2 means inconclusive and counts as a failure).

What to open: the inventory and the test baseline before any edit, the workflow with one child per module (report-service, notification-service, legacy-portal) and auth-service measured on its own, the gate (`exit 0`, seven modules measured), the transcript (27 cases), the one pre-existing legacy-portal test-order failure that Devin left alone and documented after the persona said so, and the Devin Review flag about a stale comment that Devin fixed in a follow-up commit.

### 3b. The iOS app calls the wrong host

Session (macOS): https://partner-workshops.devinenterprise.com/sessions/127cc31e664c477e893e7374212b8341. PR: https://github.com/Cognition-Partner-Workshops/otterworks/pull/1838.

Say first: "The bug report says the iPhone app cannot log in on the Simulator. Devin had to reproduce it before it was allowed to change anything."

Tests: 3, 4 (the Capacitor config, the Simulator, Web Inspector, a packet capture and a listener on the Mac, read together), 5 (the request has to reach the listener).

What to open: the Web Inspector capture of the request to `10.0.2.2` pending for five minutes, the empty listener log and the 44 unanswered SYN packets, the fix (localhost on iOS, `10.0.2.2` on Android, the environment override kept), the unit test, the after capture with the request reaching `127.0.0.1:8080`, and the note that a physical iPhone still needs the override.

### 4. File-service coverage, measured before and after

Session: https://partner-workshops.devinenterprise.com/sessions/2bb06bc59c8d4b5ea2e7be08400ea336. PR: https://github.com/Cognition-Partner-Workshops/otterworks/pull/1837.

Say first: "The Rust file service had eleven tests. Nobody wanted to write the other hundred and forty."

Tests: 1, 3, 5 (`cargo llvm-cov` before and after is the number).

What to open: the before table (crate 8.20 percent of production lines, `handlers.rs` at 2 percent), the after table (93.93 percent, 150 tests), the raw `llvm-cov` totals that include test code (14.50 to 95.27 percent, the numbers an independent run reproduces), `cargo fmt` and `clippy` clean, and the orphaned-blob behaviour Devin observed in `delete_file`, which it pinned in a test and named as a follow-up.

### 4b. The permanently red CI job

Session: https://partner-workshops.devinenterprise.com/sessions/86e34b0d39a145d49ab35e3941e5ea08. PR: https://github.com/Cognition-Partner-Workshops/otterworks/pull/1835.

Say first: "The document-service CI job failed on every run and everyone had stopped reading it. We asked Devin for the root cause before any green badge."

Tests: 3, 4 (the tests, the fixtures, the source and the git history), 5 (nine failures to zero without touching production code).

What to open: the reproduction on `main` (`9 failed, 67 passed`), the git history that points at the commit which flipped the versions order and tightened auth, the fix in the test file only (`76 passed`), the forty timer-suite runs (twenty normal, twenty under constrained CPU) with their pass counts, and the one question Devin asked: is oldest-first the contract? The persona checked the source history and said yes.

### 4c. The public pages under axe

Session: https://partner-workshops.devinenterprise.com/sessions/0d981194ad0d435b9d1b3e3bc46bf53c. PR: https://github.com/Cognition-Partner-Workshops/otterworks/pull/1841.

Say first: "Five public pages, two widths, light and dark. Measure, fix, measure again, and leave a gate so it stays fixed."

Tests: 1, 3, 5 (zero critical and serious violations across all twenty combinations).

What to open: the before table (contrast on the landing and privacy pages, unnamed password-toggle buttons on login and register, missing main landmark and heading), the after table at zero, the raw axe JSON before and after, the screenshots of the visible fixes, and the new Playwright accessibility spec that runs against the built pages in CI.

### 5. Trash and Download, fixed on screen

Session: https://partner-workshops.devinenterprise.com/sessions/094c5cd92dda490b8a348df573ea08c5. PR: https://github.com/Cognition-Partner-Workshops/otterworks/pull/1844.

Say first: "Two defects a user sees: delete in Trash asks nothing, and Download gives no feedback. Devin opened the app on its own desktop and showed us both before it changed a line."

Tests: 3, 5 (the defect has to be visible before and gone after).

What to open: the organization skill `otterworks-local-browser` that the persona approved from this session (Customize, then Skills; it holds the local browser-check notes a future session follows), the before pass on `main` (Download flashes a spinner and a toast, then the tab leaves the app for the raw storage URL and nothing is saved; Trash already confirms, so Devin said so instead of claiming a fix), the one question it asked (how to get a real download when storage sends no CORS headers; the persona chose the file-service `?disposition=attachment` URL), the after pass with the file saved byte for byte and the app still on the page, the failed state with a retry when storage is blocked, the keyboard-safe delete dialog that names the file, the ten before and after screenshots in the PR body, `npm test` 25 of 25, and `docker compose down -v` at the end.

### 5b. The iOS safe area

Session (macOS): https://partner-workshops.devinenterprise.com/sessions/754244b91ac64cd189413f85c18d6e1b. PR: https://github.com/Cognition-Partner-Workshops/otterworks/pull/1833.

Say first: "The native iPhone shell draws the header under the Dynamic Island. Devin built the app, ran it on an iPhone 16 Pro simulator and found that the covered buttons were not only hidden but unreachable."

Tests: 3, 5 (every screen, both orientations, light and dark).

What to open: the before screenshots per screen (landing, terms, privacy, login, register), the touch that the status-bar band swallowed, the two-file fix in the web layer, the after screenshots, and the recording attached to the session.

### 6. Scanner findings, reachable or noise

Session: https://partner-workshops.devinenterprise.com/sessions/f202c81fe00e44138928e2386d17fd93. PR: https://github.com/Cognition-Partner-Workshops/otterworks/pull/1830.

Say first: "A scanner export with eight findings landed on the team. We asked which ones an attacker can reach, and for the real ones, a fix with proof."

Tests: 1, 4 (the finding, the source, the running service and the probe suite), 5 (the DAST probe has to fail on `main` and pass on the branch).

What to open: the verdict table with one line of evidence per finding, the three reachable ones (error-based SQL injection in the document list, path traversal in exports, an MD5 share token anyone can compute offline), each with the request on `main` and on the branch, the probes flipping from FAIL to PASS, the ones Devin called noise and why, the two it handed to the platform team, and the Devin Review on the PR. The document-service CI job on this PR is red for the nine pre-existing test failures that act 4b fixes.

### 7. Devin's own scan of the repository

Scan: https://partner-workshops.devinenterprise.com/org/partner-demo-viewonly/security/9f52a79455a64f71a9962ac77c389507 (41 open findings, 3 critical, 13 high, 19 medium, 6 low). Fix session: https://partner-workshops.devinenterprise.com/sessions/784a231c8d5f446e9a8cab522a49e808. PR: https://github.com/Cognition-Partner-Workshops/otterworks/pull/1840.

Say first: "The persona started a security scan from the scan page. Devin read the findings and took the highest one that was not already in flight: search results leaking across users."

Tests: 1, 4, 5 (the cross-user request has to return nothing on the branch).

What to open: the scan page with the findings by severity, the finding Devin picked and the ones it skipped (the criticals are in PR #1830 or in the admin-service that does not boot on `main` by design), the reproduction of one user searching another user's documents and of the indexing endpoint answering without a service token, the fix, the search-service tests (70) and the gateway tests, the Devin Review with three findings and Devin's reply to each, and the Compose cleanup.

### 8. The tester plants the fault and the automation answers the page

Tester: https://partner-workshops.devinenterprise.com/sessions/6a2e76fe839c41318e5e3c2b6e866cbc. Responder: https://partner-workshops.devinenterprise.com/sessions/5c1861f7088e44559198df7e5208fa0f. Automation: https://partner-workshops.devinenterprise.com/org/partner-demo-viewonly/automations/auto-97756484092a420fbff31e83e94caa7b (run as the organization, webhook from Alertmanager). PR: https://github.com/Cognition-Partner-Workshops/otterworks/pull/1832.

Say first: "Nobody trusts an on-call automation until someone has tried to break it. We asked one Devin session to be that someone."

Tests: 2, 4 (Prometheus, Jaeger, the Alertmanager payload and the source in one place), 6.

What to open: in the tester, the arm of the n-plus-one scenario, the alert firing 95 seconds later, the Alertmanager `Notify success` line and the responder appearing ten minutes later with no human prompt. In the responder, the plain-language instructions on the automation page and the `!incident_responder` playbook behind them, the trace with 111 spans of which 100 are the same query, the batched query in the PR, and the honest after gate. Then back in the tester: statements per request from 98 to 5, and p95 still around 1.4 seconds against the 0.5 second bar, so the tester calls the gate red. Say that out loud; an on-call worker that reports a red gate is the point. The automation paged twice when the alert re-fired, so a second responder opened https://github.com/Cognition-Partner-Workshops/otterworks/pull/1834 with the same change; leave it closed in the demo.

## Before you present

1. Sign in through Field Kit with area `Product, leadership and partner` and identity `Pre-Sales Solution Architect`.
2. The sidebar shows only sessions that persona owns. If a session is missing, you are signed in as the wrong persona. The two automation responders are owned by the organization, so open them from the links above.
3. The recordings and screenshots are attachments on each session or images in the pull request body.
4. Nothing in the portfolio merges to `main`. The pull requests are the artifact.

## Cleanup

Nothing in this portfolio lives in a cloud account. Every session ran its stack on its own machine with Docker Compose and shut it down before it finished; the sessions say so in their last message and the audit checked `docker ps` where the session left output. The organization keeps three durable pieces on purpose: the automation `otterworks-incident-responder (Alertmanager page)`, which runs as the organization with a limit of 30 ACU per run and three runs an hour, the playbook `Answer a production alert as the first responder` (`!incident_responder`), and the playbook `Extract one legacy billing module into billing-service with parity`. Disable the automation if you do not want a stray Alertmanager to start a session. The webhook secret was rotated after the run and the old one returns 403. The branches behind PRs #1830 to #1841 and the guide PR stay until the PRs are closed.

## Known limits

- The on-call after gate is red on p95. The fix removes the N+1 (98 statements to 5) and halves the latency, but on a two-CPU host the document list stays near 1.3 seconds at the harness's 24 concurrent clients, above the 0.5 second bar. The tester's two runs and an independent rerun agree.
- The organization owns the two automation responders, because the automation API accepts only organization, creator or service-user identities. The persona owns the playbook and the tester.
- The `document-service` CI job is red on PRs #1830, #1832, #1834 and #1839 for the nine pre-existing test failures that PR #1835 fixes.
- `CodeQL` is red on the three billing PRs (#1831, #1842, #1843). It flags the MD5 helper that rebuilds the legacy row ids; parity depends on it and nobody on the persona's side can dismiss the alert, so each PR body records it as a known legacy-compatibility exception. Every other check on those PRs is green.
- On the Trash and Download act, `main` already confirms Delete and Empty Trash (the QA report predates commit a324a50d). Devin said so instead of claiming a fix, and tightened the dialog. The Download done state reads "Download started" because the app never sees when the browser finishes a cross-origin download.
- The migration PR (#1845) went green on its second CI run. The `dependency-scan` job had flagged two starlette advisories on the first, so the PR worker moved starlette to 1.3.1 and FastAPI to 0.135.4 and re-ran the transcript replay and the smoke test; that upgrade is beyond the translation itself and the parent says so. The last ticket stays In review until a human reviews the PR. It is a 40-file PR: open the body and the Accepted differences list, and leave the diff closed.
- The persona hit the enterprise default of 100 ACU per user per cycle at 03:55 UTC on 2026-10-07 and every running session paused. The persona was moved to the uncapped `FieldKit` tier and the sessions resumed with one line each. The pause is visible in the timelines.
