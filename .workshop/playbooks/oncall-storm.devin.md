# Playbook: Answer an on-call alert storm from the page to closure

> **Facilitator / author:** this file is the source for a **Devin Playbook**.
> Copy its contents into the Demo organization (Settings, then Playbooks, then *Create
> a new Playbook*) so sessions can invoke it as `!oncall_storm`, and point the
> storm Automation's prompt at that macro (`docs/oncall-storm/automation.md`).
> See [Creating Playbooks](https://docs.devin.ai/product-guides/creating-playbooks)
> and [Automations](https://docs.devin.ai/product-guides/automations).

## Overview

Use this playbook when Alertmanager pages you with one grouped notification
holding many alerts across several services. You are the on-call responder for
the whole group. Nobody types a follow-up prompt, and the people in the incident
channel (an SRE and an incident manager) talk to you only through the channel.

Twelve alerts on four services almost never have twelve causes. Your job is to
find the one change that started the storm, prove it in the database, fix it
on the fix branch, show the storm does not come back under the same load, and
hand the incident manager an RCA they can close on.

You work in `Cognition-Partner-Workshops/otterworks`, and its `oncall-storm`
skill (`.agents/skills/oncall-storm/SKILL.md`) has every command referenced
below, with the exact namespaces, Secret names and port-forwards.

## Required from user

The page carries everything the session needs:

- **The webhook body**, an Alertmanager v4 group: `groupKey`, `status`,
  `commonLabels` (`namespace`, `oncall_group`, `branch`, `fix_branch`,
  `page`), and `alerts[]`, each with `labels.alertname`, `labels.service`,
  `labels.severity`, `annotations` (`summary`, `description`,
  `dashboard_url`, `runbook_url`) and `startsAt`.
- **Org secrets** `$INCIDENT_CHANNEL_TOKEN` (bearer token for the incident
  channel API) and AWS credentials for cluster `otterworks-dev`.

If the body's `status` is `resolved`, post nothing and stop. If you were started
by a human, ask only for the webhook body.

## Posting to the channel

Send every channel post with `channel_post` below, which URL-encodes the
`groupKey` because it contains braces, quotes and spaces.

```bash
channel_post() { # channel_post <text> [image-url ...]
  jq -n --arg t "$1" --arg u "$SESSION_URL" --arg s "$SESSION_ID" --arg o "$ORG_ID" \
    '{author: "Devin", text: $t, session_url: $u, session_id: $s, org_id: $o,
      attachments: $ARGS.positional}' --args "${@:2}" |
  curl -fsS -X POST \
    "https://incident.demo.otterworks.app/api/threads/$(jq -rn --arg k "$GROUP_KEY" '$k|@uri')/messages" \
    -H "Authorization: Bearer ${INCIDENT_CHANNEL_TOKEN}" \
    -H 'Content-Type: application/json' --data-binary @- >/dev/null
}
```

Keep the token out of the session log: no `echo`, no shell tracing, and no
copy of the command with the token expanded.

## Procedure

1. Bind to the thread and acknowledge. Set `GROUP_KEY` to the payload's
   `groupKey`, and `SESSION_ID`, `ORG_ID`, `SESSION_URL` to this session's
   identity. Post one line to the channel, for example "Paged on 12 alerts in
   `otterworks-oncall-before` across web-edge, api-gateway, document-service and
   postgres. Reading telemetry now."
   Post it with `channel_post` from "Posting to the channel" above. The first
   post binds the thread to this session so SRE replies reach you.
2. Read the whole page before any single alert. List the alerts by service
   and severity, note the earliest `startsAt`, and write down which alerts are
   symptoms (edge and gateway 5xx and latency) and which point at a resource
   (pool, statement timeouts, digest backlog, Postgres CPU, connections, long
   queries). Read `docs/oncall-storm/runbook.md` for the first checks of each.
3. Get cluster access and the port-forwards. Run
   `aws eks update-kubeconfig --name otterworks-dev --region us-east-1`, then
   start the Prometheus, Grafana, Loki and Tempo port-forwards from the skill.
   Read Grafana's admin user from Secret `monitoring/grafana-admin` into
   environment variables only.
4. Optional fan-out. When child sessions are available, start two with the
   page and the skill. Both are read-only: they post nothing to the channel,
   edit no files and push nothing. Give them one brief each.
   - *logs and deploy history*: Loki error lines for the namespace grouped by
     event (`db_statement_timeout`, `folder_digest_job_failed`, pool timeouts)
     with counts and first timestamps, plus `helm history document-service` and
     `helm get values` diffs between the last two revisions;
   - *traces and query plan*: three slow `GET /api/v1/documents/` traces from
     Tempo with the time split between pool wait and SQL, plus the
     `EXPLAIN (ANALYZE, BUFFERS)` output of the slowest statement from step 6.

   Each child returns its findings with numbers and timestamps. Keep working on
   steps 5 to 7 yourself while they run, then combine their findings with yours.
   If a child fails or times out, do its half yourself.
5. Read telemetry with numbers. From Prometheus and the `oncall-storm`
   dashboard (namespace variable set to the paging namespace), write down: the
   folder-list p95 and 5xx ratio at document-service, api-gateway and the edge;
   pool checked-out against capacity; statement timeouts per second split by
   `source`; digest queue depth and oldest job age; Postgres CPU throttling,
   active connections and the `documents` sequential scan rate. From Loki, the
   count of `db_statement_timeout` lines and the statement prefix they carry.
   From Tempo, one slow trace and where its time goes.
6. Prove it in the database. Exec into the tenant Postgres (skill command)
   and list the active statements from `pg_stat_activity` and the top entries of
   `pg_stat_statements`. Run `EXPLAIN (ANALYZE, BUFFERS)` on the digest count
   and on the folder listing, each with a real `folder_id`. Record the plan
   node (`Seq Scan on documents`), `Rows Removed by Filter`, shared buffers
   read and execution time. Check `\d documents` for the indexes that exist.
7. Check what changed. Run `helm -n <namespace> history document-service`
   and `helm -n <namespace> get values document-service --revision <n>` for the
   last two revisions. Match the newest revision time against the earliest
   `startsAt` and the Grafana deploy annotation. Note that the image tag did
   not change between revisions when that is the case.
8. Write the root cause once. One paragraph tying every alert to one cause,
   for example: revision N turned on the folder digest worker, whose per-folder
   `count(*), max(updated_at)` runs a sequential scan of 200,000 rows because
   `documents.folder_id` has no index; 400 of those every 15 s on a 1 CPU
   Postgres saturate the CPU and the 5-connection pool the API shares, so
   folder listings wait, hit the 3 s statement timeout and return 500 at every
   hop. Say which alerts are symptoms and which are the cause, and what the
   fix is and is not (turning the worker off stops the storm but leaves the
   folder listing unindexed).
9. Open the incident record. Create a GitHub issue in
   `Cognition-Partner-Workshops/otterworks` titled
   `Incident: folder-storm in <namespace>`, labelled `incident` when the label
   exists, with the alert list, the timeline (deploy, first alert, page), the
   root cause paragraph and the evidence from steps 5 to 7. Post the root
   cause and the issue link to the channel.
10. Write the fix on the fix branch. Fetch `origin/<fix_branch>`
    (`demo-oncall-after`) and branch from it as `devin/<timestamp>-oncall-folder-index`.
    Never branch from `main` and never touch `demo-oncall-before`. Add
    `services/document-service/alembic/versions/005_documents_folder_index.py`
    (revision `005`, down revision `004`) creating
    `ix_documents_folder_id_updated_at` on `documents (folder_id, updated_at DESC)`,
    with a downgrade that drops it, and the same index on the `Document` model.
    Add a regression test following `tests/test_migrate.py` that upgrades to
    `005`, asserts the index exists with those columns, and asserts the plan of
    the folder count query uses it. Run `ruff` and the focused tests.
11. Open the PR. Base `demo-oncall-after`, title after the root cause, body
    with the RCA, the before numbers from steps 5 and 6, the link to the issue,
    and a line saying a human reviewer merges it. Leave merge and auto-merge to
    that reviewer, and keep `main` out of it. Post the PR link to the channel.
12. Prove the fix under the same load. Apply migration 005 from your branch
    to the `oncall-after` tenant Postgres (skill command, through a port-forward,
    with the database URL read from Secret `oncall-postgres` into an environment
    variable). Then run `make oncall-arm TENANT=oncall-after`, which seeds the
    same 200,000 documents, ships the same config deploy that turned the worker
    on, and starts the same 6-VU k6 Job. After at least 5 minutes of load, run
    `make oncall-verify TENANT=oncall-after EXPECT=after` until it is green, and
    run `make oncall-verify TENANT=oncall-before EXPECT=before` for the
    side-by-side. Run `EXPLAIN (ANALYZE, BUFFERS)` again on `oncall-after` and
    record the index scan and its execution time.
13. Capture the screenshots. In the browser, open
    `https://grafana.otterworks.app/d/oncall-storm?var-namespace=otterworks-oncall-before`
    and the same dashboard with `otterworks-oncall-after`, over the same time
    range, and screenshot both. Screenshot the k6 summary from
    `kubectl -n otterworks-oncall-after logs job/oncall-k6` once the Job has
    printed it (the `K6_SUMMARY_JSON` line and the table above it). Upload each
    image as an attachment and keep the returned URLs.
14. Post the RCA. One channel message with the Grafana screenshots attached:
    what users saw, the root cause, the evidence (plan before and after, pool,
    CPU), the fix in one sentence, before and after numbers from the two verify
    reports (p95, 5xx ratio, alerts firing), and the PR and issue links. Post the
    same RCA as a comment on the issue.
15. Act on steering. Keep watching for messages from the channel. They
    arrive in this session as user messages from the SRE or the incident
    manager persona. Act on each one, then reply in the thread with what you
    changed. The expected SRE reply asks for the index to be built
    `CONCURRENTLY` because `documents` is hot: change migration 005 to run in
    `op.get_context().autocommit_block()` with `postgresql_concurrently=True`
    on create and drop, cover it in the test, push to the same PR, downgrade
    `oncall-after` to `004` and upgrade it again while the k6 load runs, and
    re-run the after verify. Post the result, including that listings kept
    serving during the build.
16. Close through the incident manager. When the incident manager says the
    incident is closed, post a final line with the issue and PR links and the
    final after-verify result, add the closing note to the issue and close it,
    then run `make oncall-disarm TENANT=oncall-after`. Leave `oncall-before`
    armed for the presenter and leave the PR open.

## Specifications (postconditions)

- The channel thread holds, in order: the acknowledgement, the root cause with
  the issue link, the PR link, the RCA with screenshots, a reply to each SRE
  message, and the closing line. No candidate theories.
- The RCA quotes measured numbers from before and after: folder-list p95,
  alerts firing, the `EXPLAIN` execution time with the plan node for each.
- `make oncall-verify TENANT=oncall-before EXPECT=before` and
  `make oncall-verify TENANT=oncall-after EXPECT=after` both went green, and
  both report files are named in the PR body.
- The PR targets `demo-oncall-after`, contains migration 005, the model index
  and one regression test, and nothing else. It is open and unmerged.
- No commit went to `main` or `demo-oncall-before`, and no alert rule,
  threshold, seed, k6 script or harness file changed.
- The GitHub issue holds the RCA and is closed only after the incident manager
  closed the incident.

## Advice and pointers

- The storm started with a config deploy while the image tag stayed the same.
  `helm history` shows it, and the Grafana annotation names the revision.
- The worker turned the slow query into a storm, and the listing endpoint runs
  the same unindexed filter. The index fixes both, so the after tenant can run
  the worker with the index in place.
- Pool saturation and statement timeouts show the time being spent. Follow
  them to the statement, then to the plan, to see why.
- Raising the pool size, the CPU limit or the statement timeout makes the
  alerts quieter and the database busier. Say so if a reply suggests it.
- A green after gate with the worker off proves nothing. `verify.sh after`
  fails when the worker is off or the load is not running.
- Keep the thread short. The issue and the PR hold the detail.

## Forbidden actions

- Do **not** merge, enable auto-merge, or push to `main`, `demo-oncall-before`
  or `demo-oncall-after`. The PR is the deliverable.
- Do **not** silence, edit or inhibit the alerts, and do not change thresholds,
  the seed, the k6 script or `incident/oncall/` files to get a green gate.
- Do **not** turn the worker off on `oncall-before` as the fix, and do not run
  `make oncall-reset` or `make oncall-teardown`.
- Do **not** print, log, post or commit `$INCIDENT_CHANNEL_TOKEN`, the Grafana
  password, the database URL, the JWT secret or any other credential.
- Do **not** ask anyone in the channel what to do next. Act on what they say.
