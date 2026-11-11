# fees-billing / fee-reversal

## 1. Summary

- Declared process name: `halvergate.fees-billing.fee-reversal` [`integration/legacy-bw6/Processes/fees-billing/fee-reversal.bwp:L2`](../../../../legacy-bw6/Processes/fees-billing/fee-reversal.bwp#L2)
- File: `integration/legacy-bw6/Processes/fees-billing/fee-reversal.bwp`
- Declared steps inside `Execute` [`integration/legacy-bw6/Processes/fees-billing/fee-reversal.bwp:L11`](../../../../legacy-bw6/Processes/fees-billing/fee-reversal.bwp#L11): `Receive` [`integration/legacy-bw6/Processes/fees-billing/fee-reversal.bwp:L13-L14`](../../../../legacy-bw6/Processes/fees-billing/fee-reversal.bwp#L13-L14) → `MapRecord` [`integration/legacy-bw6/Processes/fees-billing/fee-reversal.bwp:L18-L19`](../../../../legacy-bw6/Processes/fees-billing/fee-reversal.bwp#L18-L19) → `Insertfeereversals` [`integration/legacy-bw6/Processes/fees-billing/fee-reversal.bwp:L23-L24`](../../../../legacy-bw6/Processes/fees-billing/fee-reversal.bwp#L23-L24) → `Publish` [`integration/legacy-bw6/Processes/fees-billing/fee-reversal.bwp:L28-L29`](../../../../legacy-bw6/Processes/fees-billing/fee-reversal.bwp#L28-L29).
- Variables `Receive` / `DispatchResponse` [`integration/legacy-bw6/Processes/fees-billing/fee-reversal.bwp:L4`](../../../../legacy-bw6/Processes/fees-billing/fee-reversal.bwp#L4); `DispatchResponse` is declared but no activity uses it (no HTTP activity in the file).

**Inference** (from names [`integration/legacy-bw6/Processes/fees-billing/fee-reversal.bwp:L23`](../../../../legacy-bw6/Processes/fees-billing/fee-reversal.bwp#L23) [`integration/legacy-bw6/Transforms/fee-reversal.xsl:L4`](../../../../legacy-bw6/Transforms/fee-reversal.xsl#L4)): each inbound reversal request is rendered with status `FEE_REVERSAL`, stored in `fee_reversals` and published to `HB.FEE.REVERSED`. The amount is passed through as received (no sign inversion and no lookup of the original posting is present in the project).

## 2. Trigger / starter activity

| Attribute | Value | Evidence |
|---|---|---|
| Activity type | `bw.jms.JMSQueueReceiver` | [`integration/legacy-bw6/Processes/fees-billing/fee-reversal.bwp:L14`](../../../../legacy-bw6/Processes/fees-billing/fee-reversal.bwp#L14) |
| Connection | `SharedResources/EmsConnection.sharedresource` | [`integration/legacy-bw6/Processes/fees-billing/fee-reversal.bwp:L14`](../../../../legacy-bw6/Processes/fees-billing/fee-reversal.bwp#L14) |
| Destination | queue `HB.FEE.REVERSAL` | [`integration/legacy-bw6/Processes/fees-billing/fee-reversal.bwp:L14`](../../../../legacy-bw6/Processes/fees-billing/fee-reversal.bwp#L14) |
| Ack mode | `CLIENT_ACKNOWLEDGE` | [`integration/legacy-bw6/Processes/fees-billing/fee-reversal.bwp:L14`](../../../../legacy-bw6/Processes/fees-billing/fee-reversal.bwp#L14) |
| Delivery mode | `PERSISTENT` | [`integration/legacy-bw6/Processes/fees-billing/fee-reversal.bwp:L14`](../../../../legacy-bw6/Processes/fees-billing/fee-reversal.bwp#L14) |
| Selector | empty | [`integration/legacy-bw6/Processes/fees-billing/fee-reversal.bwp:L14`](../../../../legacy-bw6/Processes/fees-billing/fee-reversal.bwp#L14) |
| Durable subscriber | empty | [`integration/legacy-bw6/Processes/fees-billing/fee-reversal.bwp:L14`](../../../../legacy-bw6/Processes/fees-billing/fee-reversal.bwp#L14) |
| Sequencing key | `accountId` | [`integration/legacy-bw6/Processes/fees-billing/fee-reversal.bwp:L14`](../../../../legacy-bw6/Processes/fees-billing/fee-reversal.bwp#L14) |

## 3. Transports

| Direction | Endpoint | Detail | Shared resource |
|---|---|---|---|
| Inbound | JMS queue `HB.FEE.REVERSAL` | see §2 | `EmsConnection`: provider `EMS`, url `tcp://broker:61616`, user `${EMS_USER}`, password `${EMS_PASSWORD}`, clientID `halvergate-records`, XA connection factory `XAConnectionFactory`, deliveryMode `PERSISTENT`, durableSubscription `records-event-fanout`, maxRedelivery `3`, undeliveredQueue `HB.UNDLV` [`integration/legacy-bw6/SharedResources/EmsConnection.sharedresource:L2`](../../../../legacy-bw6/SharedResources/EmsConnection.sharedresource#L2) |
| Outbound | JDBC table `fee_reversals` | `INSERT INTO fee_reversals (flow,request_id,account_id,amount,currency,status) VALUES (?,?,?,?,?,?)`, `AUTO_COMMIT` [`integration/legacy-bw6/Processes/fees-billing/fee-reversal.bwp:L24`](../../../../legacy-bw6/Processes/fees-billing/fee-reversal.bwp#L24); `fee_reversals` columns `flow, request_id, account_id, amount numeric(18,2), currency, status`, all `NOT NULL`, primary key `(flow, request_id)` [`integration/legacy-bw6/Database/schema.sql:L131-L139`](../../../../legacy-bw6/Database/schema.sql#L131-L139) | `LedgerJdbc`: driver `org.postgresql.xa.PGXADataSource`, url `jdbc:postgresql://integration-db:5432/integration`, user `${DB_USER}`, password `${DB_PASSWORD}`, transactionType `XA` [`integration/legacy-bw6/SharedResources/LedgerJdbc.sharedresource:L2`](../../../../legacy-bw6/SharedResources/LedgerJdbc.sharedresource#L2) |
| Outbound | JMS queue `HB.FEE.REVERSED` | `QUEUE`, `PERSISTENT`, properties `requestId,accountId,JMSXGroupID,sequence` [`integration/legacy-bw6/Processes/fees-billing/fee-reversal.bwp:L29`](../../../../legacy-bw6/Processes/fees-billing/fee-reversal.bwp#L29) | `EmsConnection` |

- No HTTP, SFTP or Java activity in the file ([`integration/legacy-bw6/Processes/fees-billing/fee-reversal.bwp:L1-L33`](../../../../legacy-bw6/Processes/fees-billing/fee-reversal.bwp#L1-L33)).
- Parameter/body bindings not declared; **Inference** from the recorder [`integration/legacy-bw6/reference/record.py:L55-L56`](../../../../legacy-bw6/reference/record.py#L55-L56) [`integration/legacy-bw6/reference/record.py:L65-L68`](../../../../legacy-bw6/reference/record.py#L65-L68).

## 4. Transaction boundaries

- No `bpws:scope` or transaction group exists in the file; the `Execute` sequence is flat [`integration/legacy-bw6/Processes/fees-billing/fee-reversal.bwp:L11`](../../../../legacy-bw6/Processes/fees-billing/fee-reversal.bwp#L11). For contrast, `payments.instruction-intake` declares `bpws:scope name="PostingTransaction" tibex:transactionType="XA" tibex:transactionTimeout="60"` [`integration/legacy-bw6/Processes/payments/instruction-intake.bwp:L12`](../../../../legacy-bw6/Processes/payments/instruction-intake.bwp#L12); nothing equivalent is present here.
- The JDBC insert runs with `commitMode=AUTO_COMMIT` [`integration/legacy-bw6/Processes/fees-billing/fee-reversal.bwp:L24`](../../../../legacy-bw6/Processes/fees-billing/fee-reversal.bwp#L24) even though `LedgerJdbc` declares `transactionType XA` [`integration/legacy-bw6/SharedResources/LedgerJdbc.sharedresource:L2`](../../../../legacy-bw6/SharedResources/LedgerJdbc.sharedresource#L2) and the EMS connection names an `XAConnectionFactory` [`integration/legacy-bw6/SharedResources/EmsConnection.sharedresource:L2`](../../../../legacy-bw6/SharedResources/EmsConnection.sharedresource#L2).
- The inbound message is consumed with `CLIENT_ACKNOWLEDGE` [`integration/legacy-bw6/Processes/fees-billing/fee-reversal.bwp:L14`](../../../../legacy-bw6/Processes/fees-billing/fee-reversal.bwp#L14); no explicit `JMSConfirm acknowledge=true` on the success path is present in the file (the only `JMSConfirm` is the fault handler's `acknowledge=false` [`integration/legacy-bw6/Processes/fees-billing/fee-reversal.bwp:L7`](../../../../legacy-bw6/Processes/fees-billing/fee-reversal.bwp#L7)). **Inference**: acknowledgement on success is implicit at job completion.
- Outside any boundary (**Inference** from the above): the row is committed by the insert before the `Publish` to the output queue [`integration/legacy-bw6/Processes/fees-billing/fee-reversal.bwp:L29`](../../../../legacy-bw6/Processes/fees-billing/fee-reversal.bwp#L29) and before the inbound message is acknowledged. A failure in `Publish` leaves the committed row without an output message; the redelivered message would then hit the primary key `(flow, request_id)` on re-insert.
- No call-process step follows the publish, so no steps run after a boundary ends.

## 5. XSLT chain

1. `MapRecord` — `bw.xml.TransformXML`, stylesheet `Transforms/fee-reversal.xsl`, `inputVariable Receive` [`integration/legacy-bw6/Processes/fees-billing/fee-reversal.bwp:L19`](../../../../legacy-bw6/Processes/fees-billing/fee-reversal.bwp#L19).
   - `fee-reversal.xsl` (XSLT 3.0 [`integration/legacy-bw6/Transforms/fee-reversal.xsl:L2`](../../../../legacy-bw6/Transforms/fee-reversal.xsl#L2)) imports `common/receipt.xsl` [`integration/legacy-bw6/Transforms/fee-reversal.xsl:L3`](../../../../legacy-bw6/Transforms/fee-reversal.xsl#L3) and only overrides `$status = 'FEE_REVERSAL'` [`integration/legacy-bw6/Transforms/fee-reversal.xsl:L4`](../../../../legacy-bw6/Transforms/fee-reversal.xsl#L4).
   - imports `Transforms/common/receipt.xsl` (no further imports or includes in that file; searched [`integration/legacy-bw6/Transforms/common/receipt.xsl:L1-L17`](../../../../legacy-bw6/Transforms/common/receipt.xsl#L1-L17)):
     - `xsl:output method="xml" omit-xml-declaration="yes" indent="no"` [`integration/legacy-bw6/Transforms/common/receipt.xsl:L3`](../../../../legacy-bw6/Transforms/common/receipt.xsl#L3)
     - default `$status` = `'RECEIVED'` [`integration/legacy-bw6/Transforms/common/receipt.xsl:L4`](../../../../legacy-bw6/Transforms/common/receipt.xsl#L4) (overridden by the importing stylesheet)
     - named template `status` emits `$status` [`integration/legacy-bw6/Transforms/common/receipt.xsl:L5`](../../../../legacy-bw6/Transforms/common/receipt.xsl#L5)
     - named template `amount` emits `@amount` [`integration/legacy-bw6/Transforms/common/receipt.xsl:L6`](../../../../legacy-bw6/Transforms/common/receipt.xsl#L6)
     - named template `date` emits `@timestamp` unchanged (no timezone normalisation) [`integration/legacy-bw6/Transforms/common/receipt.xsl:L7`](../../../../legacy-bw6/Transforms/common/receipt.xsl#L7)
     - root template applies templates to `request` [`integration/legacy-bw6/Transforms/common/receipt.xsl:L8`](../../../../legacy-bw6/Transforms/common/receipt.xsl#L8)
     - `match="request"` builds `<result id account currency sequence>` with `<status>`, `<amount>`, `<timestamp>` and `<body>` = `@flow|@id|@account|status|amount|date` [`integration/legacy-bw6/Transforms/common/receipt.xsl:L9-L15`](../../../../legacy-bw6/Transforms/common/receipt.xsl#L9-L15)

- Stylesheet matches the process name; no mismatch observed.

## 6. Custom Java activities

None ([`integration/legacy-bw6/Processes/fees-billing/fee-reversal.bwp:L1-L33`](../../../../legacy-bw6/Processes/fees-billing/fee-reversal.bwp#L1-L33) has no `bw.java.JavaInvoke`).

## 7. Error paths

- `catchAll` fault handler, sequence `RollbackAndRedeliver`, single activity `RejectDelivery` (`bw.jms.JMSConfirm`, `acknowledge=false`, `maxRedelivery=3`, `undeliveredQueue=HB.UNDLV`) [`integration/legacy-bw6/Processes/fees-billing/fee-reversal.bwp:L5-L10`](../../../../legacy-bw6/Processes/fees-billing/fee-reversal.bwp#L5-L10). No other fault handler, compensation handler or `catch` for specific faults exists in the file.
- Process attributes `suppressJoinFailure="yes"`, `exitOnStandardFault="no"` [`integration/legacy-bw6/Processes/fees-billing/fee-reversal.bwp:L2`](../../../../legacy-bw6/Processes/fees-billing/fee-reversal.bwp#L2).
- The shared EMS connection repeats `maxRedelivery 3` / `HB.UNDLV` [`integration/legacy-bw6/SharedResources/EmsConnection.sharedresource:L2`](../../../../legacy-bw6/SharedResources/EmsConnection.sharedresource#L2). The replay fixture broker uses `max-delivery-attempts 4` (1 + 3 redeliveries) and dead-letter address `HB.UNDLV` [`integration/fixture/broker.xml:L20-L21`](../../../../fixture/broker.xml#L20-L21).
- `HB.UNDLV` is not read by any process: it appears in Processes only as the `undeliveredQueue` of the 24 `JMSConfirm` fault handlers (searched `integration/legacy-bw6/Processes/**/*.bwp` for `HB.UNDLV`).
- Work already done when a later step fails (**Inference** from §4): a `Publish` failure leaves the `fee_reversals` row committed; redeliveries then fail on the primary key [`integration/legacy-bw6/Database/schema.sql:L138`](../../../../legacy-bw6/Database/schema.sql#L138) until the message lands on `HB.UNDLV`. A transform failure leaves nothing persisted.
- No fault evidence recorded for this flow: `"faults": {}` [`integration/corpus/fees-billing.fee-reversal/flow.json:L101`](../../../../corpus/fees-billing.fee-reversal/flow.json#L101).

## 8. Module properties per environment

| Property | Where used | dev value | prod value | Differs? |
|---|---|---|---|---|
| `${EMS_USER}` / `${EMS_PASSWORD}` | `EmsConnection` [`integration/legacy-bw6/SharedResources/EmsConnection.sharedresource:L2`](../../../../legacy-bw6/SharedResources/EmsConnection.sharedresource#L2) | not present in the project (no global variable of that name in [`integration/legacy-bw6/Profiles/dev.substvar:L2`](../../../../legacy-bw6/Profiles/dev.substvar#L2)) | not present in the project ([`integration/legacy-bw6/Profiles/prod.substvar:L2`](../../../../legacy-bw6/Profiles/prod.substvar#L2)) | unknown — **Inference**: supplied from the runtime environment |
| `${DB_USER}` / `${DB_PASSWORD}` | `LedgerJdbc` [`integration/legacy-bw6/SharedResources/LedgerJdbc.sharedresource:L2`](../../../../legacy-bw6/SharedResources/LedgerJdbc.sharedresource#L2) | not present in the project ([`integration/legacy-bw6/Profiles/dev.substvar:L2`](../../../../legacy-bw6/Profiles/dev.substvar#L2)) | not present in the project ([`integration/legacy-bw6/Profiles/prod.substvar:L2`](../../../../legacy-bw6/Profiles/prod.substvar#L2)) | unknown — **Inference**: supplied from the runtime environment |
| broker url `tcp://broker:61616`, JDBC url `jdbc:postgresql://integration-db:5432/integration` | hard-coded in the shared resources [`integration/legacy-bw6/SharedResources/EmsConnection.sharedresource:L2`](../../../../legacy-bw6/SharedResources/EmsConnection.sharedresource#L2) [`integration/legacy-bw6/SharedResources/LedgerJdbc.sharedresource:L2`](../../../../legacy-bw6/SharedResources/LedgerJdbc.sharedresource#L2) | same literal | same literal | no (not profile-driven) |

The profiles define only `screening.url`, `billing.url`, `files.url` and `notifications.url` [`integration/legacy-bw6/Profiles/dev.substvar:L2`](../../../../legacy-bw6/Profiles/dev.substvar#L2) [`integration/legacy-bw6/Profiles/prod.substvar:L2`](../../../../legacy-bw6/Profiles/prod.substvar#L2).

No profile global variable is referenced directly by this process.

## 9. Callers and callees

- Call-process edges out: none. Call-process edges in: none. Every `bw.internal.callprocess` target in the project: `account-events.account-opened`, `.address-changed`, `.limit-changed`, `.account-closed` [`integration/legacy-bw6/Processes/account-events/event-fanout.bwp:L34`](../../../../legacy-bw6/Processes/account-events/event-fanout.bwp#L34) [`integration/legacy-bw6/Processes/account-events/event-fanout.bwp:L39`](../../../../legacy-bw6/Processes/account-events/event-fanout.bwp#L39) [`integration/legacy-bw6/Processes/account-events/event-fanout.bwp:L44`](../../../../legacy-bw6/Processes/account-events/event-fanout.bwp#L44) [`integration/legacy-bw6/Processes/account-events/event-fanout.bwp:L49`](../../../../legacy-bw6/Processes/account-events/event-fanout.bwp#L49); `payments.validation-enrichment`, `.sanctions-screening`, `.currency-routing`, `.status-update` [`integration/legacy-bw6/Processes/payments/instruction-intake.bwp:L43`](../../../../legacy-bw6/Processes/payments/instruction-intake.bwp#L43) [`integration/legacy-bw6/Processes/payments/instruction-intake.bwp:L48`](../../../../legacy-bw6/Processes/payments/instruction-intake.bwp#L48) [`integration/legacy-bw6/Processes/payments/instruction-intake.bwp:L53`](../../../../legacy-bw6/Processes/payments/instruction-intake.bwp#L53) [`integration/legacy-bw6/Processes/payments/instruction-intake.bwp:L58`](../../../../legacy-bw6/Processes/payments/instruction-intake.bwp#L58); `statements-documents.split-enrich`, `.pdf-request`, `.document-store`, `.delivery-notice` [`integration/legacy-bw6/Processes/statements-documents/statement-drop.bwp:L39`](../../../../legacy-bw6/Processes/statements-documents/statement-drop.bwp#L39) [`integration/legacy-bw6/Processes/statements-documents/statement-drop.bwp:L44`](../../../../legacy-bw6/Processes/statements-documents/statement-drop.bwp#L44) [`integration/legacy-bw6/Processes/statements-documents/statement-drop.bwp:L49`](../../../../legacy-bw6/Processes/statements-documents/statement-drop.bwp#L49) [`integration/legacy-bw6/Processes/statements-documents/statement-drop.bwp:L54`](../../../../legacy-bw6/Processes/statements-documents/statement-drop.bwp#L54). No `fees-billing.*` process is named.
- Producers to `HB.FEE.REVERSAL`: no process in the project (only occurrence [`integration/legacy-bw6/Processes/fees-billing/fee-reversal.bwp:L14`](../../../../legacy-bw6/Processes/fees-billing/fee-reversal.bwp#L14)); replay corpus input [`integration/corpus/fees-billing.fee-reversal/flow.json:L5`](../../../../corpus/fees-billing.fee-reversal/flow.json#L5).
- Consumers of `HB.FEE.REVERSED`: none in the project (only occurrence [`integration/legacy-bw6/Processes/fees-billing/fee-reversal.bwp:L29`](../../../../legacy-bw6/Processes/fees-billing/fee-reversal.bwp#L29)); corpus capture [`integration/corpus/fees-billing.fee-reversal/flow.json:L39-L43`](../../../../corpus/fees-billing.fee-reversal/flow.json#L39-L43).
- Table `fee_reversals`: written only here; no reader in the project. No link to `fee_postings` exists in the schema (no foreign keys) [`integration/legacy-bw6/Database/schema.sql:L131-L139`](../../../../legacy-bw6/Database/schema.sql#L131-L139).

## 10. Reference evidence

- `cases.json` entry: input `HB.FEE.REVERSAL`, output `HB.FEE.REVERSED`, kind `""` (plain), table `fee_reversals`, two JMS cases [`integration/legacy-bw6/reference/cases.json:L516-L551`](../../../../legacy-bw6/reference/cases.json#L516-L551).
- Inputs: `fee-reversal-01` (USD 125.50, seq 1) [`integration/legacy-bw6/reference/inputs/fees-billing.fee-reversal/fee-reversal-01.xml:L2`](../../../../legacy-bw6/reference/inputs/fees-billing.fee-reversal/fee-reversal-01.xml#L2); `fee-reversal-02` (EUR 84.25, seq 2) [`integration/legacy-bw6/reference/inputs/fees-billing.fee-reversal/fee-reversal-02.xml:L2`](../../../../legacy-bw6/reference/inputs/fees-billing.fee-reversal/fee-reversal-02.xml#L2).
- Corpus expected messages `FEE_REVERSAL|125.50`, `FEE_REVERSAL|84.25` [`integration/corpus/fees-billing.fee-reversal/flow.json:L57-L78`](../../../../corpus/fees-billing.fee-reversal/flow.json#L57-L78); rows (positive amounts as received) [`integration/corpus/fees-billing.fee-reversal/flow.json:L79-L98`](../../../../corpus/fees-billing.fee-reversal/flow.json#L79-L98).
- `LegacyReference.java`: no special branch (plain stylesheet run) [`integration/legacy-bw6/reference/src/main/java/com/halvergate/reference/LegacyReference.java:L24-L30`](../../../../legacy-bw6/reference/src/main/java/com/halvergate/reference/LegacyReference.java#L24-L30).

## 11. Conversion notes

**Proposed classification: `straight-conversion`.**

Reasons: JMS queue in → one XSLT (status override only) → one insert → one publish; no Java, no HTTP, no profile-dependent values, deterministic output fully covered by the corpus (messages + rows) [`integration/corpus/fees-billing.fee-reversal/flow.json:L56-L99`](../../../../corpus/fees-billing.fee-reversal/flow.json#L56-L99).

Non-blocking notes to carry into the target (preserve as-is unless a reviewer decides otherwise):
- Transaction gap shared by all fee flows: `AUTO_COMMIT` insert before publish, no XA scope [`integration/legacy-bw6/Processes/fees-billing/fee-reversal.bwp:L24`](../../../../legacy-bw6/Processes/fees-billing/fee-reversal.bwp#L24) [`integration/legacy-bw6/SharedResources/LedgerJdbc.sharedresource:L2`](../../../../legacy-bw6/SharedResources/LedgerJdbc.sharedresource#L2).
- Orphan endpoints: no in-project producer for `HB.FEE.REVERSAL` / consumer for `HB.FEE.REVERSED` (§9).
- Amount is not negated and not validated against an existing posting (§1 Inference) — semantics to confirm with the business, but the legacy behaviour is unambiguous.
