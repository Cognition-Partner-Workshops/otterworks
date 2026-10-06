# Messaging reliability sandbox

Exercises the failure and recovery path of the production module
`infrastructure/terraform/modules/messaging` without touching anything shared:

```
SNS <token>-events-dev -> SQS <token>-analytics-events-dev --(maxReceiveCount 5)--> <token>-analytics-events-dlq-dev
                                   |                                                     |  StartMessageMoveTask
                                   v                                                     v
                     consumer (scripts/lib/sandbox_messaging.py) --> DynamoDB <token>-analytics-ledger
```

The module is instantiated with `project = <token>`, so every queue, topic,
alarm and table is new and named after the token. State is local, one file per
token and phase, under `~/.otterworks-sandbox/<token>/` (never in the repo).
No imports, no data sources on shared resources, no IAM, and the alarms have no
actions. Every resource carries `run_token=<token>` and `Expires=<RFC 3339>`
through `default_tags`.

`before/` is the same stack built from the module at `c2332d0e`, where
`analytics_events` and `search_indexing` had no dead-letter queue. It is only
there to show the defect; its names carry a `-b` suffix and it has its own state.

## Commands

Tokens look like `rs-<yyyymmdd>-<two letters>`. Use the engineer role for
`up`/`destroy` and the builder role (or engineer) for the drill:

```bash
source <(cloudworker/assume.sh engineer devin-<session id>)
make sbx-plan  RUN=rs-20261006-ab                      # plan + guard: creates only, all names start with the token
make sbx-up    RUN=rs-20261006-ab EXPIRES=2026-10-07T20:00:00Z
make sbx-drill RUN=rs-20261006-ab COUNT=5              # fail -> DLQ -> verify fails -> redrive -> verify exactly-once
make sbx-status RUN=rs-20261006-ab                     # depths, redrive policies, alarm states
make sbx-replay RUN=rs-20261006-ab                     # redrive + consume + verify on its own
make sbx-reset  RUN=rs-20261006-ab                     # purge the token's queues, empty the ledger
make sbx-up           RUN=rs-20261006-ab PHASE=before  # optional: the unrepaired module
make sbx-before-drill RUN=rs-20261006-ab PHASE=before  # receive count climbs past 5, nothing captures it
make sbx-destroy      RUN=rs-20261006-ab CONFIRM=rs-20261006-ab   # both phases, then verify-clean
make sbx-verify-clean RUN=rs-20261006-ab               # tagging API + name-prefix lookups, exits 1 if anything remains
```

`up` saves the plan, runs `plan-guard` on `terraform show -json` (rejects
deletes, replacements, imports, drift, names or `run_token` tags outside the
token) and applies exactly that saved plan. `destroy` does the same with
`-destroy`.

## What the drill proves

1. `reset`, then publish `COUNT` `file_uploaded` events with distinct `eventId`s.
2. Consume with an injected ledger outage: each receive fails and is made visible
   again at once, until SQS moves every event to the DLQ after 5 receives.
3. `verify` must fail here: the ledger has none of the events.
4. `redrive` starts `StartMessageMoveTask` on the DLQ (destination omitted, so
   back to the original source queue) and waits for `COMPLETED`.
5. Consume with one crash per message between the durable write and the ack, so
   every event is delivered twice; the conditional `TransactWriteItems`
   (`attribute_not_exists(pk)` + `ADD events :one`) applies it once.
6. `verify` passes only if every published id is in the ledger, the rollup
   counter equals the number of events, and both queues are empty.

The DLQ depth alarm should move to `ALARM` within a few minutes of step 2
(CloudWatch SQS metrics are per minute) and back to `OK` after step 4; check
with `sbx-status`.

## Offline tests

`make sbx-test` runs the module and sandbox `terraform test` suites (mocked
provider), the driver tests against moto, and the stubbed shell tests. None of
them call AWS.
