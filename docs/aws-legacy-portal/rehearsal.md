# Rehearsal on 2026-10-05

Run token `lp-20261005-rh`, region `us-east-1`, against the placeholder functions. The transcripts are in `rehearsal/lp-20261005-rh/`, copied from `.demo/legacy-portal/lp-20261005-rh/` with the account number already replaced by `<account>`.

## Measured numbers

| Step | Command | Started (UTC) | Wall clock | Result |
|---|---|---|---|---|
| Up | `make lp-up RUN=lp-20261005-rh` | 08:00:11 | 476 s (7.9 min) | 34 added, 7 min of it on the Aurora writer |
| Up again | `make lp-up RUN=lp-20261005-rh` | 08:08:24 | 13 s | No changes |
| Status | `make lp-status RUN=lp-20261005-rh` | 08:08:37 | 13 s | 16 tagged resources, cluster available at 0 to 1 ACU |
| Reset | `make lp-reset RUN=lp-20261005-rh CTX=all` | 08:09:07 | 6 s | Three tables empty, ids from 1 |
| First replay | `make lp-replay RUN=lp-20261005-rh CTX=all STAGE=first` | 08:09:14 | 6 s | Every context stopped at its first case |
| Down | `make lp-down RUN=lp-20261005-rh` | 08:09:26 | 727 s (12.1 min) | 34 destroyed |
| Verify clean | `make lp-verify-clean RUN=lp-20261005-rh` | 08:21:35 | 43 s | `CLEAN` |

The first `up.log` ends with a shell syntax error on line 214 after `lp-up wall clock: 476 s`. The apply had finished; the error came from editing `scripts/lp-serverless.sh` while that run was still reading it, and the transcript records `exit=2` for that reason. The second run, `up-rerun.log`, uses the final script and exits 0 with no changes.

## First replay

| Context | Cases in corpus | Stopped at | Java | Placeholder |
|---|---|---|---|---|
| common | 10 | `common-01` `GET /health` | 200 with the status body | 501 |
| announcements | 36 | `ann-01` `GET /api/announcements` | 200 `[]` | 501 |
| preferences | 20 | `pref-01` `GET /api/preferences/newuser` | 200 with the defaults | 501 |
| feedback | 29 | `fb-01` `GET /api/feedback/average-rating` | 200 `{"averageRating": 0.0}` | 501 |

That is the pause state the run of show starts from: the stack is up, the replay runs, and nothing has been ported yet. The per-context evidence is in `rehearsal/lp-20261005-rh/replay-first/` and the table in `replay-first-summary.md`.

Before the AWS run, the same `replay.py` ran in full against the Java service built from `main` and running locally in Docker on PostgreSQL 15. It reported 95 of 95 identical (common 10, announcements 36, preferences 20, feedback 29), so the harness and the normalisation agree with the recording.

## Aurora capacity and cost

CloudWatch `ServerlessDatabaseCapacity` for the cluster read 1.0 ACU from 08:04 to 08:10, while the schema and the reset ran, and 0.5 ACU from 08:11 to 08:20 while it sat idle and awake. It never reached the 600 idle seconds needed to pause before `lp-down` removed it. The sum of the per-minute averages is about 11.6 ACU minutes, or 0.19 ACU hours.

The AWS Price List API, read at 08:22:37 UTC, gives Aurora PostgreSQL Serverless v2 in `us-east-1` at $0.12 per ACU hour (publication date 2026-10-01). The compute for the whole rehearsal therefore comes to about $0.02.

| State | Capacity | Compute per hour |
|---|---|---|
| Paused, after 600 idle seconds | 0 ACU | $0.00 |
| Awake and idle, as measured | 0.5 ACU | $0.06 |
| At the ceiling | 1 ACU | $0.12 |

Storage, I/O, the secret, the functions and the API are billed on top by use and were not measured separately.

## Builder policy

`rehearsal/lp-20261005-rh/builder-policy-simulation.log` holds the IAM policy simulator results for `devin-cw-builder` while the run was applied. Updating the run's own feedback function, running Data API statements on the run's cluster, reading its secret and its logs, and patching a route on the run's API were allowed. The same calls against a function tagged with another token, a function outside the run, another API, deleting the cluster and passing the execution role were all denied.

## Baseline after teardown

Read at 08:23:06 UTC, after `lp-verify-clean`.

| Check | Result |
|---|---|
| `aws iam list-attached-role-policies --role-name devin-cw-builder` | `ReadOnlyAccess` only, as before the run |
| `aws iam list-role-policies --role-name devin-cw-builder` | The existing inline policy `devin-cw-builder` |
| `aws ec2 describe-vpcs` and `describe-subnets` | VPC `otterworks-dev` and both private subnets available |
| Security groups tagged `demo=legacy-portal-serverless` in that VPC | 0 |
| `aws rds describe-db-clusters` | No clusters |
| Tagging API for `demo=legacy-portal-serverless` | 0 resources |

One object stays behind: the empty state file `otterworks/legacy-portal-serverless/lp-20261005-rh/terraform.tfstate` (406 bytes, no resources) in the versioned bucket `otterworks-terraform-state`, the same way the other Terraform roots in the repo keep their state.
