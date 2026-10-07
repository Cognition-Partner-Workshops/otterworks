# The presenter guide for Devin as a legacy modernization engineer

This guide is for the person who opens the Partner Demo - ViewOnly organization in front of an architecture or modernization audience and talks for twenty to forty minutes. Every item you show is a Devin session that the Legacy Modernization Engineer persona started, or a worker, ticket or child behind one. You sign in through the Field Kit SSO page with area `Engineering` and identity `Legacy Modernization Engineer`, and that persona's sidebar is the demo. Nothing here needs a cloud account: every session worked on source code, containers on its own machine, a Windows or macOS machine, GitHub Actions or one of Devin's own surfaces.

## The beliefs the audience leaves with

A modernization program is a quality problem before it is a coding problem. The audience should leave with three beliefs, and every session below earns at least one of them.

1. Devin raises quality and holds a standard. Characterization tests run before any change, every move has a parity gate, Devin Review runs on every pull request, and one named target standard (the organization skill `modernization-target-standard`) is what every worker is measured against.
2. Devin does the same thing many times without drift. A dynamic workflow runs over a module count nobody typed, a playbook is run by three children, and a Migrations board is worked by small sessions, one ticket each.
3. Devin is the contextual engineer in the room. An estate assessment with waves and risks comes before any code moves, the decisions go to the human instead of being taken silently, and DeepWiki and the organization's skills are read before every change.

Say the three beliefs once at the start and name the one each session shows before you open it.

## The delegation tests

Before you open a session, say which of these the work passes.

1. The judgment is easy and the volume is the hard part.
2. The same job comes back for every module, every script, every batch job.
3. The job is tedious, and nobody on the team wants to be the one who does it.
4. A person cannot hold the context: the code, the running service, the wiki, the old platform and the new one at once.
5. A gate says done (a parity table, a `cmp`, a reconciliation, a screenshot pair), so the agent keeps going until the gate passes or says plainly that it failed.
6. The job blocks someone more expensive, like a licence renewal date or a support end date.

## The eight acts

| Act | What the audience worries about | Devin surface |
|---|---|---|
| 0. Estate assessment | What do we even have, and in which order do we move it | Ask Devin with DeepWiki, a report PR |
| 1. Framework upgrade sweep | Java 8 and Spring Boot 2 across many modules | Dynamic workflow with one worker per module |
| 2. Monolith extraction | Pulling one module out without breaking the rest | One session, strangler route, Helm chart |
| 3. Cron to Airflow | Scripts on a box with no tests | Migrations board worked by worker sessions |
| 4. Mainframe batch offload | ksh, Perl and awk jobs nobody wants to read | A playbook run by three children |
| 5. Oracle takeout | A licence renewal next quarter | One session with a reconciliation gate |
| 6. Windows desktop | A .NET Framework 4.8 client | A Windows session machine |
| 7. iOS shell | An Xcode project two platform versions behind | A macOS session machine |

## The sessions in presenting order

### 0. The estate assessment and the wave plan

Session: https://partner-workshops.devinenterprise.com/sessions/e2eebf62c5584c9dacc45de4b26f7f38. PR: https://github.com/Cognition-Partner-Workshops/otterworks/pull/1873.

Say first: "Before anyone touches code, we asked Devin what we have, what is out of support, and in which order we should move it."

Tests: 3, 4 (the DeepWiki, two branches, every manifest and Dockerfile), 6 (support end dates).

What to open: the prompt; the DeepWiki pages Devin lists in section 1 of `docs/modernization/assessment.md`, with the places where the wiki disagrees with the code; the inventory table with runtime, framework, support status and dependencies; one pattern per workload; the one question Devin asked before finishing (which estate goes first); and the answer, which pulled the Oracle takeout and the CUSTBILL offload into Wave 1 because the licence renewal is next quarter. Show section 6, where Devin wrote down what changed with the answer and what still needs confirming. The PR changes one file and makes no code change.

### 1. The framework upgrade sweep, as a dynamic workflow

Parent session: https://partner-workshops.devinenterprise.com/sessions/e2dcd3a501374bec807c8ccaeecf4f34. Discovery: https://partner-workshops.devinenterprise.com/sessions/bfc42e56b1fa44ab86c0f60b92b896eb.

Workers and PRs:

| Module | From | To | Tests before | Tests after | Worker | PR |
|---|---|---|---|---|---|---|
| report-service | Java 8, Spring Boot 2.5.15, javax | Java 21, Spring Boot 3.3.13, jakarta | 71 passed | 70 passed, 1 failed | [09982430](https://partner-workshops.devinenterprise.com/sessions/09982430ad944876874de40145c552f0) | [#1880](https://github.com/Cognition-Partner-Workshops/otterworks/pull/1880) |
| legacy-portal | Java 11, Spring Boot 2.7.18, javax | Java 21, Spring Boot 3.3.13, jakarta | 50 passed | 50 passed | [3d89e9f5](https://partner-workshops.devinenterprise.com/sessions/3d89e9f5b8fc481680f7092ba5282508) | [#1878](https://github.com/Cognition-Partner-Workshops/otterworks/pull/1878) |
| auth-service | Java 17, Spring Boot 3.2.4 | Java 21, Spring Boot 3.3.13 | 59 passed | 59 passed | [01a4685e](https://partner-workshops.devinenterprise.com/sessions/01a4685ef4754a18a946d73b02d1e0bb) | [#1877](https://github.com/Cognition-Partner-Workshops/otterworks/pull/1877) |
| analytics-service | Java 17, Scala 3.4, Akka HTTP | Java 21, same framework | 42 passed | 42 passed | [b80a74d7](https://partner-workshops.devinenterprise.com/sessions/b80a74d7a19f4c79910d7c6bc9a4eedb) | [#1874](https://github.com/Cognition-Partner-Workshops/otterworks/pull/1874) |
| notification-service | Java 17, Kotlin 1.9, Ktor 2.3 | Java 21, same framework | 34 passed | 34 passed | [7716a313](https://partner-workshops.devinenterprise.com/sessions/7716a313b5dc4b54830485987f2f319a) | [#1888](https://github.com/Cognition-Partner-Workshops/otterworks/pull/1888) |

Say first: "Nobody told Devin how many modules were behind. A discovery agent counted them, and one worker took each module."

Tests: 1, 2, 5 (the characterization suite runs against the old build first and is the gate for the new one).

What to open: the discovery output with the count (nine JVM modules read, five qualify) and the reason for each; the workers in flight in the parent; then one worker end to end. Open legacy-portal (#1878) for the clean story: a 50-test live HTTP suite passes on the old build, the first upgraded run fails one test because Spring Framework 6 stopped matching trailing slashes, Devin adds one config class, and the same 50 tests pass. Then open report-service (#1880) for the honest story: two parity rows stay failed (Swagger 2 has no Boot 3 implementation, and a dependency lab case needs the Nashorn engine that JDK 21 removed), and Devin left them red and asked instead of rewriting the lab's evidence. Point at the skill `modernization-target-standard` that every worker cites. Skip the analytics and notification workers unless someone asks about Scala or Kotlin: they move the JDK only and keep their framework.

### 2. User preferences out of the monolith

Session: https://partner-workshops.devinenterprise.com/sessions/e0994b76da504187b423de1279dc915e. PR: https://github.com/Cognition-Partner-Workshops/otterworks/pull/1876.

Say first: "We asked Devin to take one module out of a Spring Boot monolith, prove the callers see nothing change, and leave the rest of the monolith answering."

Tests: 3, 4 (the DeepWiki, the monolith, the extraction skill, the Helm conventions), 5 (the HTTP transcript).

What to open: the DeepWiki pages Devin read; why it picked preferences over feedback (two routes, no shared exception handler); the 95-request transcript recorded against the running monolith on `main` and replayed through the new strangler route at 95 of 95 identical; the `X-Served-By` header showing which service answered; announcements and feedback still served by the monolith; `docker-compose.portal.yml`; the Helm chart copied from `report-service` with `helm template` and `kubeconform -strict` clean; and the Devin Review threads. The persona made three decisions the review raised: the data copy stays a manual `pg_dump` step with a row-count gate after it, readiness checks the database while liveness does not, and authorization is a follow-up because parity with `main` is the point of this PR.

### 3. Cron scripts to Airflow on the Migrations board

Board: https://partner-workshops.devinenterprise.com/org/partner-demo-viewonly/migrations (`OtterWorks ETL: cron to Airflow`). Parent session: https://partner-workshops.devinenterprise.com/sessions/0f54fa9eea404c188ff6c4e140223aac.

Say first: "Five Python scripts run from cron on one box, with no tests. We typed one sentence on the Migrations page and attached the upgrade guide."

Tests: 1, 2, 5 (the goldens are the gate for every DAG).

What to open: the one sentence and the attached brief; the plan with four phases and 20 steps; the two plan defaults the persona changed before approving (the destructive audit archive runs second and alone, and every legacy script stays one weekly cycle after its DAG cuts over); the board with one ticket per step and the dependencies between them. Then the golden harness worker ([7655066199824ddcb398a52ab004b57c](https://partner-workshops.devinenterprise.com/sessions/7655066199824ddcb398a52ab004b57c), PR [#1879](https://github.com/Cognition-Partner-Workshops/otterworks/pull/1879)) and the parent's note that it moved the ticket to Done only after checking the PR's CI and running each script twice for byte-identical output. Open one golden worker, audit archive ([b83d00be](https://partner-workshops.devinenterprise.com/sessions/b83d00be81c14058a4f924b0dce044a2), PR [#1891](https://github.com/Cognition-Partner-Workshops/otterworks/pull/1891)), because its goldens found that the legacy script has never deleted anything. Devin put that on the plan as a decision with no default, and the persona picked: keep the no-op at cutover so parity holds, and put the correct delete behind an Airflow Variable that stays off until compliance signs off. The storage cleanup goldens found a second destructive bug, a key match that quarantines files still in use, and it got the same treatment. Skip the other golden workers (#1889, #1890, #1892, #1893); they are the same job four more times.

### 4. The CUSTBILL batch chain, through a playbook and its children

Parent session: https://partner-workshops.devinenterprise.com/sessions/f3330de7bb5e43feaad3494d0be0ef5f. PR: https://github.com/Cognition-Partner-Workshops/otterworks/pull/1885 (against `tech-partnerships`). Playbook: `One legacy batch job to a tested Python module with byte-identical output` (Playbooks page of the organization). Children: `sftp_ingest_poll` https://partner-workshops.devinenterprise.com/sessions/b84df583e5184c17b9c97a0c1dd8f616, `parse_custbill_fixedwidth` https://partner-workshops.devinenterprise.com/sessions/89c80e1aa15b4a0487e7ca1bbdb3ce77, `finance_excel_report` https://partner-workshops.devinenterprise.com/sessions/e313c1db1d314ab285faff307736ae68.

Say first: "Three old batch jobs in ksh, awk and Perl feed finance every morning. Devin wrote down the method once and ran it three times."

Tests: 1, 2, 3, 5 (`cmp` on every output file).

What to open: the playbook text the parent saved before starting any child; the three children, each with its own port and pytest; the parent merging their branches into its integration branch and keeping the chain runnable end to end; the parity tool that runs the legacy job and the Python job from the same input and compares every file; `cmp` with zero differences per job and for the whole chain in two namespaces (`dev` and `qa`); the SFTP fixture moving a file from drop to incoming. Then the Devin Review finding on the finance port: the legacy Perl job passes a path into shell commands, so a crafted value can run commands. Devin kept it for parity and asked; the persona told it to close the hole and record the behaviour change as an accepted difference.

### 5. Oracle billing to PostgreSQL

Session: https://partner-workshops.devinenterprise.com/sessions/fe92d581cd0b4037837780554c4f0a26. PR: https://github.com/Cognition-Partner-Workshops/otterworks/pull/1887 (against `tech-partnerships`).

Say first: "The Oracle licence renewal is next quarter and nobody wants to renew it. We asked Devin to move billing to Postgres and prove the numbers did not move."

Tests: 3, 4 (the PL/SQL packages, the schema, the data and the application at once), 5 (the reconciliation), 6 (the renewal date).

What to open: the Oracle Free container started first and seeded; the schema and PL/SQL packages translated to PostgreSQL 15 in a container of its own, away from the shared infra Postgres; the reconciliation report, one row per table and check; the orphan decision card, where Devin found 37 invoice lines with no invoice header and asked what to do with them; the answer (quarantine, so the recon reads `150000 = 149963 + 37` with the money split the same way); the 248-call replay through `legacy-billing` against both engines; and the second decision, the audit-log row that Oracle keeps after a failed call and Postgres rolled back, which the persona asked to keep the Oracle way. Close on the Oracle container stopped at the end.

### 6. The Windows desktop client to .NET 8

Session: https://partner-workshops.devinenterprise.com/sessions/b5967d1230c3434e9cefacc8eee22da4. PR: https://github.com/Cognition-Partner-Workshops/otterworks/pull/1884.

Say first: "This is a WPF client on .NET Framework 4.8. Devin ran it on a Windows machine before touching it, then converted it and ran it again."

Tests: 3, 5 (the same seven UI tests and screenshots before and after).

What to open: the Windows session machine; the local gateway stub under `tests/clients/windows-desktop/`; the before run on .NET Framework 4.8 with the five screens (register, empty documents, created document, logged out, document still there after logging in again); the conversion to an SDK-style project on `net8.0-windows` with `PackageReference`, `System.Text.Json` and nullable on; the same seven tests passing unchanged on the new build; the side-by-side table in the PR body; and the DPAPI check, where a login saved by one build is restored by the other. The tests drive a real window, so CI only builds the client.

### 7. The iOS shell platform refresh

Session: https://partner-workshops.devinenterprise.com/sessions/71103e64000d4238b3529b3aee9b37dc. PR: https://github.com/Cognition-Partner-Workshops/otterworks/pull/1886.

Say first: "The iOS shell builds, but nobody has looked at it against current Xcode. Devin ran every screen in the Simulator before and after."

Tests: 3, 5 (the screens and the warning count).

What to open: the macOS session machine; the before build and the five screens in the Simulator (landing, terms, privacy, login, register); the finding that the untouched app crashes at launch when linked against the newest SDK because it has no scene lifecycle; the deployment target raised from iOS 15 to iOS 17, the recommended Xcode settings and the move to `@main` with a `SceneDelegate`; the same screens after. Say the warning count plainly: one before and one after, the same Xcode App Intents message, and no compiler or deprecation warnings either side, so there was nothing to clear. Three layout problems on the web pages fail before and after; the PR lists them as failed instead of hiding them.

## Before you present

1. Sign in through Field Kit with area `Engineering` and identity `Legacy Modernization Engineer`.
2. The sidebar shows only sessions the persona owns, including the workflow workers, the board's ticket workers and the playbook's children. If one is missing, you are signed in as the wrong persona.
3. The recordings and screenshots are attachments on each session or images in the pull request body.
4. Nothing in the portfolio merges to `main` or `tech-partnerships`. The pull requests are the artifact.

## Cleanup

Nothing in this portfolio lives in a cloud account. Each session ran its containers on its own machine and shut them down; act 5 stopped the Oracle container at the end. The organization keeps three durable pieces on purpose: the skill `modernization-target-standard`, the playbook `One legacy batch job to a tested Python module with byte-identical output` and the Migrations board `OtterWorks ETL: cron to Airflow`. The branches behind the PRs stay until the PRs are closed.

## Known limits

- The report-service PR (#1880) is red on the `deps` job, with two failed parity rows: Swagger 2 has no Boot 3 implementation, and a dependency lab case needs Nashorn, which JDK 21 removed. The lab belongs to another demo, so the persona left both rows red.
- Act 4's three child PRs (#1881, #1882, #1883) show as merged on GitHub because the parent merged them into its own integration branch, which the act asks for. Nothing merged into `tech-partnerships`; #1885 is open.
- The act 3 golden PRs (#1889 to #1893) target the harness branch from #1879, not `main`, because they build on the harness. Their tickets say so.
- On act 7 the warning count stays at one before and after, and three web layout problems are present before and after.
- Act 1's prompt capped the sweep at four modules. The organization limit was raised during the run, and the persona sent one follow-up to run the fifth (notification-service).
- Spring Boot 3.3 is past open-source support. The organization standard names it, so the workers used it; the next target is a separate decision.
