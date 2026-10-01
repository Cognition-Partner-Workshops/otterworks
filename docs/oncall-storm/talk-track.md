# On-call storm talk track

The live segment runs about 25 minutes, from the page to the close. Times are measured from the moment you run `make oncall-arm`. Two people help: one types as the SRE in the channel, one as the incident manager. If you present alone, keep both reply boxes in a second tab.

## Before the audience arrives

At minus 15 minutes, run `make oncall-status` and check that both tenants show the worker off, nothing firing and no k6 Job. Open these tabs in order:

1. The incident channel, `https://incident.demo.otterworks.app`, logged in as `oncall`.
2. Grafana dashboard `oncall-storm` with `namespace=otterworks-oncall-before`, last 30 minutes, 10 s refresh.
3. The tenant web app, `https://t-oncall-before.demo.otterworks.app`, logged in as the demo user, opened on a folder.
4. Alertmanager filtered to `page="oncall"`.
5. The Devin sessions list in the Demo org.
6. The GitHub repository, pull requests tab.

At minus 10 minutes, run `make oncall-arm TENANT=oncall-before` in a terminal off the shared screen.

## 0:00 Opening (channel on screen)

"This is the incident channel for a document app called OtterWorks. Ten minutes ago a teammate shipped a config change, a background job that keeps folder summaries fresh. Nobody has noticed anything yet. In a few minutes this channel lights up, and the first responder is going to be Devin. Nobody here will type a prompt."

## 0:06 The storm (Grafana, then channel)

The first alerts fire about 6 minutes after the deploy. Switch to Grafana and point at the deploy annotation and the climb that follows it: folder-list p95 past 0.5 s, pool checked-out at 5 of 5, Postgres CPU throttled, statement timeouts climbing.

"Twelve alerts, four services. The edge is returning errors, the gateway is slow, the database is pinned. A human on call now opens twelve runbooks."

Switch to the channel: the card has grown to about twelve alerts with four service chips. Then Alertmanager: one group for the namespace.

## 0:09 The page (channel)

Alertmanager waits 3 minutes to group the storm, then sends one notification to the automation. Devin's acknowledgement appears in the thread within about a minute, with a link to the session.

"One page for the whole storm, and the acknowledgement came from Devin. The session started from the webhook."

Open the session from that link and show the playbook steps being followed, and the two child sessions if it fanned out.

## 0:12 The investigation (Devin session)

Show the session reading Prometheus, Loki and Tempo, then `helm history` with the revision that turned the worker on. Then the `EXPLAIN (ANALYZE, BUFFERS)` output: `Seq Scan on documents`, about 200,000 rows removed by the filter.

"It went to the database and asked the planner. Every folder count reads the whole table. Four hundred folders every 15 seconds on one CPU."

Switch to the channel: the root cause post and the GitHub issue link.

## 0:15 The fix (GitHub)

Open the pull request: base `demo-oncall-after`, migration 005 adding an index on `documents (folder_id, updated_at)`, and a regression test.

"The fix goes to the branch that feeds the after tenant. Devin does not merge it and does not touch the tenant that paged."

## 0:17 Steering (channel)

The SRE types: "documents is hot in prod, build that index concurrently." Show the message being delivered to the session, then Devin's reply in the thread a few minutes later with the updated migration pushed to the same PR.

"The SRE corrected the approach in the channel, the same way they would correct a teammate, and the change landed on the PR."

## 0:20 The proof (Grafana)

Switch the dashboard variable to `otterworks-oncall-after`, same time range. Same worker, same 200,000 documents, same 6-user k6 load, and the folder-list p95 stays under 0.5 s with nothing firing. Flip back to `otterworks-oncall-before` once for the contrast.

## 0:22 The RCA (channel and GitHub)

The RCA post in the thread: the before and after screenshots, the numbers from both verify reports, the PR and issue links. Open the issue to show the same RCA as a comment.

## 0:24 The close (channel)

The incident manager types "Closing the incident, thanks." Devin posts the closing line and closes the issue.

"Paged at minute nine, closed at minute twenty four, and the pull request is waiting for a reviewer."

## Recovery moves

| Symptom | Move |
|---|---|
| No alerts by 0:08 | `make oncall-status TENANT=oncall-before`; if k6 is not running, rerun `make oncall-arm TENANT=oncall-before` and fill time on the dashboard. |
| No Devin acknowledgement by 0:12 | `make oncall-simulate` with `ONCALL_DEVIN_WEBHOOK_URL` set, or paste `incident/oncall/simulate.sh --print` into a new session that starts with `!oncall_storm`. |
| SRE reply shows a failed tick | Paste the same text into the Devin session. |
| After tenant still red at 0:22 | Show `make oncall-verify TENANT=oncall-after EXPECT=after` output; a red gate names the failing check. |

## After the session

Run `make oncall-reset`, then close the pull request and the issue by hand. The next run is ready after about 10 minutes, once CD has redeployed any tenant whose branch moved.
