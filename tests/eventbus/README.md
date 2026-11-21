# Domain-event bus: SNS → EventBridge

Domain events (document-service, file-service) move from the SNS topic
`otterworks-events` to the EventBridge bus `otterworks-events`. Both paths run
side by side. Each publisher picks a transport with `EVENT_TRANSPORT`
(`DOC_SVC_EVENT_TRANSPORT` for document-service):

| value | behaviour |
|---|---|
| `sns` (default) | unchanged: publish to the SNS topic only |
| `dual` | publish to SNS and EventBridge |
| `eventbridge` | publish to EventBridge only |

The EventBridge rules deliver to the same consumer queues the SNS topic
feeds, so `dual` delivers every event twice to a queue that is subscribed to
both. Locally that is all four queues; on AWS it is analytics, whose SNS
subscription is unfiltered. Use `dual` only to check the bus against probe
queues. To cut over a publisher, switch it from `sns` to `eventbridge`, and
switch it back to roll back. document-service publishes only when
`DOC_SVC_SNS_ENABLED=true`, whatever the transport; `deploy-dev.sh` sets it
when `EVENT_TRANSPORT` is given.

On EventBridge, `source` is `otterworks.<service>`, `detail-type` is the event
type, and `detail` is the same JSON body the publisher sends to SNS. Consumers
(search, notification, audit, analytics) unwrap the EventBridge envelope as
well as the SNS one.

## Routing

| consumer queue | EventBridge rule |
|---|---|
| notifications | `detail-type` in `file_shared, comment_added, document_edited, user_mentioned` |
| search | `detail-type` in the types the search indexer handles |
| audit | every `otterworks.*` event |
| analytics | every `otterworks.*` event |

Every consumer queue has its own DLQ. EventBridge puts events it cannot
deliver after retries there, and SQS redrives messages consumers keep failing
on there. A CloudWatch alarm fires when any DLQ has messages.

## Running the harness

```bash
docker run -d --name ow-eb-ls -p 4566:4566 \
  -e SERVICES=s3,sqs,sns,events,dynamodb -e DEFAULT_REGION=us-east-1 \
  -v "$PWD/scripts/localstack-init.sh:/etc/localstack/init/ready.d/init.sh" \
  localstack/localstack:3.8
pip install boto3
python tests/eventbus/fanout_harness.py --transport sns --out /tmp/eb/sns
python tests/eventbus/fanout_harness.py --transport eventbridge --out /tmp/eb/eventbridge
```

The harness publishes one event of each type in the shape each publisher
sends. Then it drains every queue and writes `routing.md`, `routing.json` and
the raw bodies under `fixtures/`. For SNS it also attaches throwaway
subscriptions that carry the Terraform filter policies (`tfprobe-*`).

## Parity

Evidence is in `evidence/`. `before` is `main` with the original LocalStack setup.
`after-sns` and `after-eventbridge` are this branch.

### SNS path (default transport)

| check | before | after | result |
|---|---|---|---|
| events delivered to `otterworks-notifications` | 11/11 | 11/11 | pass |
| events delivered to `otterworks-search-events` | 11/11 | 11/11 | pass |
| events delivered to `otterworks-audit-events-queue` | 11/11 | 11/11 | pass |
| SNS message body | publisher JSON | identical | pass |
| events matched by the Terraform notifications filter | 0/11 | 0/11 | unchanged (follow-up) |
| events matched by the Terraform search filter | 0/11 | 0/11 | unchanged (follow-up) |

### EventBridge path (new)

| consumer | intended event types | delivered | result |
|---|---|---|---|
| notifications | `comment_added`, `file_shared` (of the 11 types the harness publishes) | exactly those 2 | pass |
| search | 8 indexed types published | exactly those 8 | pass |
| audit | all 11 | 11 | pass |
| analytics | all 11 | 11 | pass |
| `detail` vs SNS `Message` (audit queue) | — | 11/11 parse to the same JSON | pass |

### Unit tests (main → this branch)

| service | main | branch | result |
|---|---|---|---|
| document-service (pytest) | 67 passed, 9 failed | 73 passed, 9 failed | pass (same 9 auth failures on main, not caused by this change) |
| file-service (cargo test) | 11 passed | 13 passed | pass |
| search-service (pytest) | 41 passed | 45 passed | pass |
| notification-service (gradle test) | 33 passed | 35 passed | pass |
| audit-service (dotnet test) | 53 passed | 57 passed | pass |
| analytics-service (sbt, `service.*` and `model.*`) | 20 passed | 24 passed | pass |

## Known gaps (not fixed here)

- The SNS filter policies in `infrastructure/terraform/modules/messaging` match
  a message attribute `eventType`. document-service sends `event_type` and
  file-service sends no attributes, so on AWS the filtered notifications and
  search subscriptions receive nothing. This branch leaves the SNS path as it
  is. Switching the publishers to `eventbridge` routes these events correctly.
- analytics-service decodes `eventType/userId/resourceId/resourceType`. The
  domain events carry neither the camelCase fields nor `userId/resourceId`, so
  analytics now receives the events but does not record them. That needs a
  mapping decision.
- notification-service decodes camelCase fields (`eventType`, `fileId`, ...).
  document-service's `comment_added` is snake_case with a nested `payload`, so
  it fails to decode over SNS today and over EventBridge alike.
- audit-service records document events and file events other than
  `file_shared` with type `unknown` and empty resource IDs. The behaviour is
  the same over SNS and EventBridge.
- search-service stays `SQS_ENABLED=false` in `deploy-dev.sh` as on `main`.
  Its queue URL is now wired, so turning indexing on is a single flag.
