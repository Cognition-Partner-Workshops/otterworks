---
name: tibco-bw-to-camel
description: "Team standard for converting a BusinessWorks 6 process in OtterWorks (integration/legacy-bw6, demo-tibco) to a Spring Boot + Apache Camel route on Artemis: activity mapping, transaction and acknowledgement rules, tib: XPath replacements, the replay and fault test every flow must pass, and the PR template. Learned on the payments.instruction-intake pilot. Run token tib-d1111."
---

# BusinessWorks 6 to Camel: team standard (tib-d1111)

Learned on the pilot `halvergate.payments.instruction-intake`
(`integration/legacy-bw6/Processes/payments/instruction-intake.bwp` ->
`integration/target/payments/.../InstructionIntakeRoute.java`). Follow it for every
flow in the wave plan. A flow is only done when its replay is clean field by field
and its fault test passes, both shown as command output, never by reading code.

## Ground rules

- Work on a branch off `demo-tibco`; never `main`. Prefix commits and the PR title with `[tib-d1111]`.
- `integration/legacy-bw6/` and `integration/corpus/` are frozen and hash-locked.
  Run `python -m integration.harness verify-lock` first; never re-record, edit or
  normalise the corpus, and never change the harness to make a diff go away. If the
  target cannot match the corpus, fix the target or stop and escalate.
- Convert one BW process per route, in the target module named by the inventory
  (`integration/target/<module>`). Convert only what the BW process itself does.
  A `bw.internal.callprocess` to another inventoried flow stays out until that flow is
  converted; say so in the PR.
- Copy the process's XSLT files (and every `xsl:import`/`xsl:include` they pull in)
  into `src/main/resources/Transforms/` byte for byte. Do not rewrite a stylesheet
  into Java.
- Stack and tests: `make tibco-up NS=<ns>`, `make tibco-replay NS=<ns> FLOW=<flow>`,
  `make tibco-fault NS=<ns> TEST=<fault>`, `make tibco-down NS=<ns>`. Local only;
  no AWS, no deploy-tenant.sh.
- If Maven Central rate-limits (HTTP 429) the wrapper, set
  `MVNW_REPOURL=https://maven-central.storage-download.googleapis.com/maven2` and use a
  settings.xml mirror pointing at the same host.

## Activity mapping

| BW activityTypeID | Camel / Spring equivalent | Notes |
|---|---|---|
| `bw.jms.JMSQueueReceiver` | `from("jms:queue:<dest>?transacted=true...")` | See transaction rules. One consumer per sequencing key unless the ordering fault test proves otherwise. |
| `bw.jms.JMSTopicSubscriber` | `from("jms:topic:<dest>?subscriptionDurable=true&durableSubscriptionName=<legacy name>&clientId=<legacy id>")` | Durable name and client id must equal the legacy ones (consumer-restart fault). |
| `bw.jms.JMSConfirm` | Nothing explicit: the transaction commit is the confirm. | CLIENT_ACKNOWLEDGE + Confirm at the end of the scope == transacted consume. Never `acknowledgementModeName=AUTO_ACKNOWLEDGE`. |
| `bw.jms.JMSSendMessage` | XA-enlisted send in the same transaction (`XaStatusPublisher` pattern) or `to("jms:...")` when no literal JMSX* header is in the contract | `deliveryMode=PERSISTENT` always. See header rule below. |
| `bw.jdbc.JDBCUpdate` (`commitMode=TRANSACTION_GROUP`) | `JdbcTemplate.update(...)` on the XA DataSource inside the transacted route | Plain insert; no upsert, no "skip if exists". Same SQL and column order as the BWP. |
| `bw.jdbc.JDBCUpdate` (auto-commit) | `JdbcTemplate` on a non-XA DataSource, or `sql:` component | Only if the BWP really is outside the group. |
| `bw.xml.TransformXML` | `to("xslt-saxon:Transforms/<file>.xsl?output=DOM")` | camel-saxon-starter; XSLT 2/3. Warm the stylesheet at startup. |
| `bw.internal.callprocess` | `to("direct:<flow>")` once that flow exists; until then out of scope | Respect whether the call is inside or after the transaction scope. |
| `bw.internal.start` / `bw.jms.Timer` | `from("timer:...")` or `from("quartz:...")` | Same schedule as the legacy. |
| `bw.http.SendHTTPRequest` | `to("http:...")` with explicit timeouts | Never inside an XA scope (not a transactional resource); do it after commit or make it idempotent. |
| `bw.sftp.SFTPGet` / `SFTPPut` | `from/to("sftp:...")` | Write to a temp name and rename, matching the legacy file name exactly. |
| `bw.java.JavaInvoke` | A Spring bean called with `.bean(...)` | Port the class logic and cover it with a unit test from the corpus. |
| BWP `faultHandlers` / rollback with `maxRedelivery=N`, undelivered queue | Broker redelivery: Artemis `max-delivery-attempts = N+1`, `dead-letter-address` = legacy undelivered queue (`HB.UNDLV`) in `integration/fixture/broker.xml`; route `errorHandler(transactionErrorHandler().maximumRedeliveries(0))` | Camel must not retry in memory; the rollback returns the message to the broker, which redelivers and dead-letters. |

## Transaction and acknowledgement rules

1. A BW scope with `tibex:transactionType="XA"` becomes one JTA transaction
   (Narayana: `dev.snowdrop:narayana-spring-boot-starter`) over the JMS consume, every
   `TRANSACTION_GROUP` JDBC write and every send inside the scope. Timeout = the
   scope's `transactionTimeout`.
2. Consumer: `JmsComponent.jmsComponentTransacted(xaConnectionFactory, jtaTransactionManager)`,
   `.transacted("required")` on the route, `cacheLevelName=CACHE_NONE`,
   `exposeListenerSession=true` (otherwise Spring opens a second session and rollback
   logs `XAER_PROTO` / `ARJUNA016129`), `concurrentConsumers=1` for sequenced flows,
   short `recoveryInterval` (100 ms).
3. DataSource: XA (`PGXADataSource`); Postgres needs `max_prepared_transactions > 0`.
   After every test `SELECT count(*) FROM pg_prepared_xacts` must be 0.
4. Narayana object store on a persistent volume (`/app/transaction-logs`) so recovery
   survives a container restart; recovery period short enough to finish within the
   fault test's capture window.
5. Retry and DLQ belong to the broker (rule in the table). Never mask a redelivery by
   ignoring duplicate keys; a duplicate must be impossible because the first attempt
   rolled back.
6. Output headers are part of the corpus contract. The Artemis JMS client rewrites
   `JMSXGroupID` to `_AMQ_GROUP_ID` and adds `__AMQ_CID`; when the corpus expects the
   literal names, send through an Artemis core XA session enlisted in the current
   transaction and set the properties literally (see `XaStatusPublisher`). Strip all
   other headers before the send (`removeHeaders("*", <contract headers>)`).
7. Declare every output queue the route writes to as durable, non auto-delete, before
   consuming. Artemis auto-delete removed `HB.PAYMENT.STATUS` during a broker restart
   in the pilot and the send committed into nothing: a silent loss.
8. Start the route only after the broker, DB and transformer are ready (`autoStartup(false)` + readiness start).
9. Log `in-tx receive / inserted / published` and the transaction outcome
   (`COMMIT`/`ROLLBACK` via a transaction synchronization) with the request id; the
   fault evidence relies on these lines.

## tib: XPath functions

Look first at where the function is defined. In this estate the `tib:` functions are
defined inside the stylesheets themselves (e.g.
`Transforms/statements/base/timezone.xsl`), so the copied stylesheet keeps working
under Saxon unchanged. That is the preferred replacement: keep the stylesheet.

When a function must move into Java or plain XPath 3.1, use the first two rows. They
are the only `tib:` calls in the estate today (one call site,
`Transforms/statement.xsl:5`, flow `statements-documents.statement-drop`) and were
checked byte for byte against its corpus. The other rows are starting points that
have not been verified yet:

| BW function | XPath 3.1 (Saxon) | Java |
|---|---|---|
| `tib:parse-dateTime(x)` | `xs:dateTime(x)` | `OffsetDateTime.parse(x)` |
| `tib:format-dateTime(d,'UTC')` | `string(adjust-dateTime-to-timezone(d, xs:dayTimeDuration('PT0H')))` | `DateTimeFormatter.ISO_INSTANT.format(d.toInstant())` (verify fractional seconds against the corpus) |
| `tib:format-dateTime(d, picture)` | `format-dateTime(d, picture)` | `DateTimeFormatter.ofPattern(...)` |
| `tib:current-dateTime()` / `tib:timestamp()` | `current-dateTime()` | `OffsetDateTime.now(clock)`, injectable clock for replay |
| `tib:trim(s)` | `normalize-space(s)` (check inner spaces) or `replace(s,'^\s+|\s+$','')` | `String.strip()` |
| `tib:pad(s,n,c)` / `tib:pad-front` | `substring(concat(string-join((1 to n)!c), s), ...)` | `String.format` / `StringUtils.leftPad` |
| `tib:render-xml(n)` / `tib:parse-xml(s)` | `serialize(n)` / `parse-xml(s)` | JAXP |
| `tib:get-*` engine/process info | A route/exchange property set by Camel | Must not leak into corpus fields |

Every replacement is proved against the corpus values for that flow (run the legacy
stylesheet and the replacement, compare bytes), and Daylight Saving inputs such as
`2026-03-29T01:30:00+01:00` must stay covered.

## Test pattern every flow must pass

In the module (`integration/target/mvnw -f integration/target/pom.xml package`):
1. Transform test: load `integration/corpus/<flow>/flow.json`, run the copied
   stylesheet on every input, assert the expected output fields from the corpus (no
   hand-written expectations).
2. Transaction test with embedded Artemis + H2/Postgres XA: success writes every row and
   one output; a failure on the last write leaves no row and no output and the message
   is redelivered then dead-lettered after `max-delivery-attempts`; an empty/poison body
   dead-letters after the same count. Zero `XAER_PROTO` in the log.

Live, on the compose stack, with outputs pasted in the timeline before and after:
3. `python -m integration.harness verify-lock` passes.
4. Before: `make tibco-replay` and `make tibco-fault` on the unconverted target (expected to fail; keep the output).
5. After: `make tibco-replay NS=<ns> FLOW=<flow>` reports `Differing: 0`, `Status: matched`.
6. After: `make tibco-fault NS=<ns> TEST=broker-kill` passes with
   `expected_ids == actual_ids` (each id exactly 1), run at least 4 times from clean
   state. To prove the kill landed inside a transaction, use an opt-in hold
   (`PAYMENTS_TX_HOLD_MS`-style, default 0, first transaction only) placed after the
   last write/send and before commit, sized just above the measured receive-to-kill
   latency (pilot: 150 ms vs 97-117 ms). The log must show
   receive -> writes -> publish -> hold -> ROLLBACK -> redelivery -> COMMIT at least once.
7. After the fault: one row per id in each table, `pg_prepared_xacts` = 0, input,
   output and DLQ queues empty.
8. Also run `consumer-restart`, `poison` or `ordering` when the flow has a durable
   subscriber, a redelivery limit, or a sequencing key (one child session per fault,
   skill `tibco-fault-test`).
9. `ruff check integration`, harness tests, and `.github/workflows/tibco-parity.yml`
   extended with the flow's replay and fault steps.

## Pull request template

Title: `[tib-d1111] <flow>: BW6 -> Camel (<module>)`

```markdown
## Flow
- BW process: `<process name>` (`integration/legacy-bw6/Processes/...bwp`)
- Camel route: `<routeId>` in `integration/target/<module>/...`
- Scope converted: <transaction scope / activities>; out of scope: <call-process steps and why>

## Mapping
| BW activity | Camel | Notes |
|---|---|---|

## Transactions and acknowledgement
- Transaction: <XA/JTA resources enlisted>, timeout <s>
- Ack: <transacted consume, CACHE_NONE, exposeListenerSession>
- Redelivery/DLQ: <max-delivery-attempts>, <DLQ> (legacy maxRedelivery <n>)
- Output headers: <contract headers and how they are preserved>

## Evidence (command output, before and after)
- verify-lock: <output>
- Replay before: <Matched/Differing>  after: <Matched/Differing>
- Fault <test> before: <status>  after: <status>, <k>/<k> runs, expected_ids == actual_ids
- Transaction log excerpt: receive -> ... -> ROLLBACK -> COMMIT
- Post-fault: rows per id, pg_prepared_xacts, queue depths

## Tests
- Unit/embedded: <tests and results>
- CI workflow: <steps added>

## Not done / risks
- <untested faults, CI not yet run, follow-up flows>
```

Do not name the requester or any email in the PR; a session link is fine. Leave the
PR open; never merge it yourself.
