# Integration replay package

The runner sends frozen messages and SFTP inputs to an isolated integration environment,
captures outputs, and compares every declared field. STOMP 1.2 carries message bodies,
headers and application properties to Artemis. PostgreSQL queries capture database rows;
SFTP or a mounted directory supplies emitted files. Replay never rewrites expected outputs.

## Dependencies and commands

Run from the repository root with Python 3.11 or newer. Runtime dependencies are
`pyyaml==6.0.2`, `stomp.py==8.2.0`, `paramiko==3.5.1` and `psycopg[binary]==3.2.9`.
Run a selected flow with dependencies supplied by uv:

```sh
uv run --with pyyaml==6.0.2 --with stomp.py==8.2.0 --with paramiko==3.5.1 --with 'psycopg[binary]==3.2.9' python -m integration.harness replay --corpus integration/corpus --flow sample --report-dir integration/reports
```

With dependencies installed, verify or freeze the corpus, replay inputs, inject faults,
or regenerate reports:

```sh
python -m integration.harness verify-lock --corpus integration/corpus
python -m integration.harness record-lock --corpus integration/corpus --reason 'initial reference capture'
python -m integration.harness replay --corpus integration/corpus --flow sample --report-dir integration/reports
python -m integration.harness fault --corpus integration/corpus --flow sample --test broker-kill --report-dir integration/reports
python -m integration.harness report --input integration/reports/parity.json --report-dir integration/reports
```

Repeat `--flow` to select multiple flows; omit `--flow` to replay every flow in sorted order.
Exit codes are 0 for parity, 1 for differences or replay errors, and 2 for a refused operation.
Each invocation writes one report covering the selected flows. Keep separate report directories
for independent fault runs. `report` regenerates HTML and Markdown from saved JSON without replay.

## Corpus contract

```text
integration/corpus/
  destinations.yaml
  FIXTURE_SHA.json
  sample/
    flow.json
```

Each flow directory contains `flow.json`, and additional reference source files can be stored
beside the flow file. The lock covers every corpus file, including the YAML destination map.
`verify-lock` checks the complete path-to-SHA256 map, detecting changed, added and removed
files before opening any transport. Symlinks and empty corpora are refused.
Store reports outside the corpus. `record-lock --reason` explicitly accepts a new frozen
reference and appends the reason, UTC time and previous hashes to the lock history.
An empty reason is refused, including on initial recording. Review reference changes and
the lock together. The command freezes externally recorded outputs; the command does not
generate expected behavior by running the target implementation.

`destinations.yaml` declares physical STOMP addresses and resource connections:

```yaml
broker:
  url: stomp://localhost:61613
  username_env: REPLAY_BROKER_USER
  password_env: REPLAY_BROKER_PASSWORD
  client_id: replay-observer
  receipt_timeout: 10
sftp:
  host: localhost
  port: 2222
  username_env: REPLAY_SFTP_USER
  password_env: REPLAY_SFTP_PASSWORD
  known_hosts: /config/known_hosts
  input_root: /upload/in
db:
  dsn_env: REPLAY_DB_DSN
ignore:
  - /messages/*/headers/message-id
  - /messages/*/headers/subscription
  - /messages/*/headers/timestamp
  - /messages/*/headers/content-length
```

`url_env`, `username_env`, `password_env` and `dsn_env` read environment variables at runtime.
Direct `url`, `username`, `password` and `dsn` values are also supported, but credentials
belong in environment variables. Use `stomps://` for TLS. SFTP uses known-host verification
and supports `key_filename`; install the server host key before replay. Paths in resource
configuration refer to the runner's filesystem, independent of the corpus path.

A minimal `flow.json` with one JMS-style message looks like:

```json
{
  "inputs": {
    "messages": [{
      "destination": "input.queue",
      "body": "{\"request\":\"r1\"}",
      "properties": {"requestId": "r1", "region": "west"},
      "headers": {"persistent": "true", "correlation-id": "r1"}
    }],
    "files": [{"path": "request.txt", "base64": "b2s="}]
  },
  "publish_interval": 0.01,
  "capture_seconds": 5,
  "capture": {
    "messages": [{"id": "output", "destination": "output.queue", "headers": {}}],
    "db": {
      "requests": {
        "query": "SELECT request_id, amount FROM requests WHERE request_id = %s ORDER BY request_id",
        "params": ["r1"]
      }
    },
    "files": {"transport": "directory", "root": "/outputs/sample"}
  },
  "expected": {
    "messages": [{
      "destination": "output.queue",
      "body": "accepted",
      "headers": {"requestId": "r1", "correlation-id": "r1", "destination": "output.queue"}
    }],
    "db": {"requests": [{"request_id": "r1", "amount": "1.20"}]},
    "files": {"result.txt": "b2s="}
  },
  "ignore": []
}
```

Declare all three expected output collections even when empty: `messages: []`, `db: {}`,
`files: {}`. Message bodies are UTF-8 strings compared byte-for-byte as decoded text.
Properties and protocol headers share the STOMP header namespace. The `properties` input
map is merged first; explicit `headers` override duplicate keys. STOMP property values
are strings; typed JMS application properties require a separate adapter. Artemis maps
`correlation-id`, `reply-to`, `priority`, `expires`, `persistent` and `type` to JMS headers.
The raw `message-id` is the STOMP representation of JMSMessageID. Use Artemis's raw
`JMSXGroupID` property for sequencing groups. Configure anycast/multicast addresses and
subscription headers to match the tested deployment; the runner does not create broker topology.

Capture subscriptions start before publishing, with receipts confirming readiness. Inputs
are sent persistently by default and each SEND waits for a broker receipt. An ambiguous
SEND is never retried automatically. Captured messages include every raw header, including
application properties, and the declared destination. Topic capture can use Artemis
`durable-subscription-name` in subscription `headers` with a stable broker `client_id`.
Keep durable capture names distinct from the application's durable subscriber names.

Database query results preserve order, so use an explicit `ORDER BY`. Queries execute in
a read-only transaction. Decimal, date, timestamp and UUID values become strings; SQL NULL
becomes JSON null. Binary values become `{"base64": "..."}`. Query only the replay's
records in an isolated database or start with clean tables. The runner does not reset data.

Files use base64 for exact binary comparison, and a file capture reads every regular file
recursively under `root`, detecting unexpected files as well as missing files. Use
`{"transport": "sftp", "root": "/upload/out/sample"}` for remote output capture.
Input SFTP directories must already exist. Uploads use a `.replay-part` temporary name
and rename after upload; consumers must exclude temporary files from their file pickup.

Capture waits the full `capture_seconds` interval after the final input, then snapshots
messages, rows and files. Size the interval for the flow's retry and delivery limits;
late arrivals beyond the interval cannot be assessed. Run sequentially in clean, dedicated
queues and directories. Stale records and messages otherwise appear as extra outputs.

## Comparison and evidence

Objects compare by key, arrays compare in order and scalar types must match. Ignore patterns
are case-sensitive slash paths with shell-style wildcards, for example
`/db/requests/*/created_at`. Patterns apply only to named fields; an ignored timestamp does
not suppress a missing message or row. Message order across capture subscriptions must
be deterministic in ordinary parity runs. Fault ordering checks group by sequencing key
and permit interleaving between keys. During an ordering fault run, parity also groups
messages by key while retaining each key's observed order.

Reports contain per-flow `replayed` input counts (messages plus SFTP drops), `matched` and
`differing` outbound-message counts, status, captured outputs and one reason per differing
field. Database and file differences always fail parity even when outbound-message counts
match. Every missing or extra message contributes to the differing count. Transport errors
produce error rows, with exception types only to avoid leaking connection credentials.
Fault results and the verified fixture hashes are embedded in JSON, Markdown and HTML.
Reports contain message bodies and database rows; treat the output directory as test data.

## Fault hooks

Add a `faults` object to the selected flow so each command replays the flow and checks both
ordinary parity and the chosen fault invariant. Hooks operate on explicitly named Docker
containers in an isolated local environment; Docker access is required only for restart tests.
Containers are restarted in cleanup after publishing failures. A failed cleanup marks the
flow as an error. The runner does not alter shared infrastructure or discover containers.

```json
{
  "broker-kill": {
    "container": "isolated-broker",
    "after_message": 1,
    "downtime": 1,
    "ready_timeout": 30,
    "identity_header": "requestId"
  },
  "consumer-restart": {
    "container": "isolated-consumer",
    "after_message": 1,
    "restart_after": 3,
    "identity_header": "requestId",
    "topic": "events.topic",
    "durable_subscription": "stable-worker"
  },
  "poison": {
    "identity_header": "requestId",
    "identity": "bad-request",
    "audit_destination": "attempts.queue",
    "delivery_count_header": "deliveryCount",
    "redeliveries": 3,
    "dlq": "dead.queue"
  },
  "ordering": {
    "key_header": "JMSXGroupID",
    "sequence_header": "sequence",
    "parallel_consumers": 2
  }
}
```

`after_message` is the number of receipt-confirmed messages sent before stopping a container.
Broker kill runs `docker kill` then `docker start` during the flow and reconnects the runner
before sending the remaining inputs. Acknowledged output already captured remains in memory.
Use a persistent volume for the broker and durable capture subscriptions for topics.
The hook interrupts a flow after a confirmed SEND; the hook does not prove the consumer
was inside a transaction at the instant of the kill. The target fixture must provide
transaction timing or a barrier when an in-transaction crash is required.

Consumer restart runs `docker stop`, publishes messages while the consumer is offline, then
runs `docker start` after `restart_after` messages. The offline slice must target `topic`.
The deployment must use the declared durable subscription; the report records that configured
name as configuration only. Both restart tests require
non-empty, unique expected output identities and compare identity multiplicities to detect
loss or duplication. Provide one output per identity, or choose a unique output identity
for fan-out flows.

Poison tests require an attempt audit destination populated by the tested consumer, with
one event per attempted delivery carrying a 1-based delivery count and poison identity.
Capture the audit destination and DLQ alongside ordinary outputs. The hook checks attempts
1 through `redeliveries + 1` and exactly one poison message on the declared DLQ. A DLQ
header alone cannot prove the retry history. The runner never manufactures attempt events
or configures broker redelivery policy. The expected corpus must include the audit outputs.

Ordering tests compare the sequence-header arrays per key against expected output, catching
missing, duplicated and reordered sequence values. Declare at least two `parallel_consumers`
and run the target with that concurrency. The count is a deployment assertion, recorded in
evidence; the runner does not measure concurrency. The report fails when required headers or
fault evidence are missing. Sequence values should uniquely identify each position per key.

## Unit tests

```sh
uv run --with pyyaml==6.0.2 --with pytest==8.3.5 python -m pytest integration/harness/tests
uv run --with ruff==0.9.10 ruff check integration/harness
```

Unit tests use fake transports and container controls, so Docker and live services are
unnecessary. Live broker, database and SFTP checks belong to the consuming fixture.
