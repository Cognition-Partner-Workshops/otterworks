# BW6 conversion wave plan

Run **tib-d1111**. Scope: **24 processes**. Classification follows the remaining decisions; wave placement follows dependencies, not classification. Straight conversions can enter their wave after Wave 0; held flows enter only after their named decisions are resolved.

## Ordering rule

Convert callees before or together with callers. Call-process suffix matches are candidate bindings to verify in Wave 0. There are no in-project producer/consumer destination matches in [graph.json](graph.json); do not invent a queue pipeline. See [dependency graph](dependency-graph.md).

## Wave 0 — Groundwork (no processes)

These are preconditions for the whole programme, not individual flow blockers. Supply approved shared configuration and demonstrate parity before implementing any process. This inventory does not execute conversion or certify runtime semantics.

### Environment credentials and literal hosts

Where do per-environment credentials and host values come from? SFTP credentials apply only to statement-drop and split-enrich. Establish and verify the programme-wide contract.

- [`integration/legacy-bw6/SharedResources/EmsConnection.sharedresource:L2`](../../legacy-bw6/SharedResources/EmsConnection.sharedresource#L2) — `"${EMS_USER}"`.
- [`integration/legacy-bw6/SharedResources/EmsConnection.sharedresource:L2`](../../legacy-bw6/SharedResources/EmsConnection.sharedresource#L2) — `"${EMS_PASSWORD}"`.
- [`integration/legacy-bw6/SharedResources/EmsConnection.sharedresource:L2`](../../legacy-bw6/SharedResources/EmsConnection.sharedresource#L2) — `"tcp://broker:61616"`.
- [`integration/legacy-bw6/SharedResources/LedgerJdbc.sharedresource:L2`](../../legacy-bw6/SharedResources/LedgerJdbc.sharedresource#L2) — `"${DB_USER}"`.
- [`integration/legacy-bw6/SharedResources/LedgerJdbc.sharedresource:L2`](../../legacy-bw6/SharedResources/LedgerJdbc.sharedresource#L2) — `"${DB_PASSWORD}"`.
- [`integration/legacy-bw6/SharedResources/LedgerJdbc.sharedresource:L2`](../../legacy-bw6/SharedResources/LedgerJdbc.sharedresource#L2) — `"jdbc:postgresql://integration-db:5432/integration"`.
- [`integration/legacy-bw6/SharedResources/StatementSftp.sharedresource:L2`](../../legacy-bw6/SharedResources/StatementSftp.sharedresource#L2) — `"${SFTP_USER}"`.
- [`integration/legacy-bw6/SharedResources/StatementSftp.sharedresource:L2`](../../legacy-bw6/SharedResources/StatementSftp.sharedresource#L2) — `"${SFTP_PASSWORD}"`.
- [`integration/legacy-bw6/SharedResources/StatementSftp.sharedresource:L2`](../../legacy-bw6/SharedResources/StatementSftp.sharedresource#L2) — `"<host>sftp</host>"`.

**Inference (complete profiles and activities inspected):** neither profile defines these six credential variables; broker, database and SFTP hosts are literal strings, not profile variables. All flows use EMS credentials. JDBC credentials apply to the 22 JDBC flows, not currency-routing or pdf-request. Only statement-drop and split-enrich use SFTP. Secondary pointer: [spec](specs/statements-documents/statement-drop.md).

### Call-process binding and independent starters

Do unprefixed names resolve? Should callees be in-process subprocesses, independent queue/topic consumers, or both, and what input mapping applies? Establish and verify the programme-wide contract.

- [`integration/legacy-bw6/Processes/account-events/event-fanout.bwp:L34`](../../legacy-bw6/Processes/account-events/event-fanout.bwp#L34) — `"account-events.account-opened"`.
- [`integration/legacy-bw6/Processes/account-events/account-opened.bwp:L2`](../../legacy-bw6/Processes/account-events/account-opened.bwp#L2) — `"halvergate.account-events.account-opened"`.
- [`integration/legacy-bw6/Processes/account-events/account-opened.bwp:L14`](../../legacy-bw6/Processes/account-events/account-opened.bwp#L14) — `"HB.ACCOUNT.OPENED"`.
- [`integration/legacy-bw6/Processes/account-events/event-fanout.bwp:L39`](../../legacy-bw6/Processes/account-events/event-fanout.bwp#L39) — `"account-events.address-changed"`.
- [`integration/legacy-bw6/Processes/account-events/address-changed.bwp:L2`](../../legacy-bw6/Processes/account-events/address-changed.bwp#L2) — `"halvergate.account-events.address-changed"`.
- [`integration/legacy-bw6/Processes/account-events/address-changed.bwp:L14`](../../legacy-bw6/Processes/account-events/address-changed.bwp#L14) — `"HB.ADDRESS.CHANGED"`.
- [`integration/legacy-bw6/Processes/account-events/event-fanout.bwp:L44`](../../legacy-bw6/Processes/account-events/event-fanout.bwp#L44) — `"account-events.limit-changed"`.
- [`integration/legacy-bw6/Processes/account-events/limit-changed.bwp:L2`](../../legacy-bw6/Processes/account-events/limit-changed.bwp#L2) — `"halvergate.account-events.limit-changed"`.
- [`integration/legacy-bw6/Processes/account-events/limit-changed.bwp:L14`](../../legacy-bw6/Processes/account-events/limit-changed.bwp#L14) — `"HB.LIMIT.CHANGED"`.
- [`integration/legacy-bw6/Processes/account-events/event-fanout.bwp:L49`](../../legacy-bw6/Processes/account-events/event-fanout.bwp#L49) — `"account-events.account-closed"`.
- [`integration/legacy-bw6/Processes/account-events/account-closed.bwp:L2`](../../legacy-bw6/Processes/account-events/account-closed.bwp#L2) — `"halvergate.account-events.account-closed"`.
- [`integration/legacy-bw6/Processes/account-events/account-closed.bwp:L14`](../../legacy-bw6/Processes/account-events/account-closed.bwp#L14) — `"HB.ACCOUNT.CLOSED"`.
- [`integration/legacy-bw6/Processes/payments/instruction-intake.bwp:L43`](../../legacy-bw6/Processes/payments/instruction-intake.bwp#L43) — `"payments.validation-enrichment"`.
- [`integration/legacy-bw6/Processes/payments/validation-enrichment.bwp:L2`](../../legacy-bw6/Processes/payments/validation-enrichment.bwp#L2) — `"halvergate.payments.validation-enrichment"`.
- [`integration/legacy-bw6/Processes/payments/validation-enrichment.bwp:L14`](../../legacy-bw6/Processes/payments/validation-enrichment.bwp#L14) — `"HB.PAYMENT.VALIDATION"`.
- [`integration/legacy-bw6/Processes/payments/instruction-intake.bwp:L48`](../../legacy-bw6/Processes/payments/instruction-intake.bwp#L48) — `"payments.sanctions-screening"`.
- [`integration/legacy-bw6/Processes/payments/sanctions-screening.bwp:L2`](../../legacy-bw6/Processes/payments/sanctions-screening.bwp#L2) — `"halvergate.payments.sanctions-screening"`.
- [`integration/legacy-bw6/Processes/payments/sanctions-screening.bwp:L14`](../../legacy-bw6/Processes/payments/sanctions-screening.bwp#L14) — `"HB.SANCTIONS.REQUEST"`.
- [`integration/legacy-bw6/Processes/payments/instruction-intake.bwp:L53`](../../legacy-bw6/Processes/payments/instruction-intake.bwp#L53) — `"payments.currency-routing"`.
- [`integration/legacy-bw6/Processes/payments/currency-routing.bwp:L2`](../../legacy-bw6/Processes/payments/currency-routing.bwp#L2) — `"halvergate.payments.currency-routing"`.
- [`integration/legacy-bw6/Processes/payments/currency-routing.bwp:L14`](../../legacy-bw6/Processes/payments/currency-routing.bwp#L14) — `"HB.CURRENCY.ROUTING"`.
- [`integration/legacy-bw6/Processes/payments/instruction-intake.bwp:L58`](../../legacy-bw6/Processes/payments/instruction-intake.bwp#L58) — `"payments.status-update"`.
- [`integration/legacy-bw6/Processes/payments/status-update.bwp:L2`](../../legacy-bw6/Processes/payments/status-update.bwp#L2) — `"halvergate.payments.status-update"`.
- [`integration/legacy-bw6/Processes/payments/status-update.bwp:L14`](../../legacy-bw6/Processes/payments/status-update.bwp#L14) — `"HB.STATUS.UPDATE"`.
- [`integration/legacy-bw6/Processes/statements-documents/statement-drop.bwp:L39`](../../legacy-bw6/Processes/statements-documents/statement-drop.bwp#L39) — `"statements-documents.split-enrich"`.
- [`integration/legacy-bw6/Processes/statements-documents/split-enrich.bwp:L2`](../../legacy-bw6/Processes/statements-documents/split-enrich.bwp#L2) — `"halvergate.statements-documents.split-enrich"`.
- [`integration/legacy-bw6/Processes/statements-documents/split-enrich.bwp:L14`](../../legacy-bw6/Processes/statements-documents/split-enrich.bwp#L14) — `"HB.STATEMENT.SPLIT"`.
- [`integration/legacy-bw6/Processes/statements-documents/statement-drop.bwp:L44`](../../legacy-bw6/Processes/statements-documents/statement-drop.bwp#L44) — `"statements-documents.pdf-request"`.
- [`integration/legacy-bw6/Processes/statements-documents/pdf-request.bwp:L2`](../../legacy-bw6/Processes/statements-documents/pdf-request.bwp#L2) — `"halvergate.statements-documents.pdf-request"`.
- [`integration/legacy-bw6/Processes/statements-documents/pdf-request.bwp:L14`](../../legacy-bw6/Processes/statements-documents/pdf-request.bwp#L14) — `"HB.PDF.REQUEST"`.
- [`integration/legacy-bw6/Processes/statements-documents/statement-drop.bwp:L49`](../../legacy-bw6/Processes/statements-documents/statement-drop.bwp#L49) — `"statements-documents.document-store"`.
- [`integration/legacy-bw6/Processes/statements-documents/document-store.bwp:L2`](../../legacy-bw6/Processes/statements-documents/document-store.bwp#L2) — `"halvergate.statements-documents.document-store"`.
- [`integration/legacy-bw6/Processes/statements-documents/document-store.bwp:L14`](../../legacy-bw6/Processes/statements-documents/document-store.bwp#L14) — `"HB.DOCUMENT.STORE"`.
- [`integration/legacy-bw6/Processes/statements-documents/statement-drop.bwp:L54`](../../legacy-bw6/Processes/statements-documents/statement-drop.bwp#L54) — `"statements-documents.delivery-notice"`.
- [`integration/legacy-bw6/Processes/statements-documents/delivery-notice.bwp:L2`](../../legacy-bw6/Processes/statements-documents/delivery-notice.bwp#L2) — `"halvergate.statements-documents.delivery-notice"`.
- [`integration/legacy-bw6/Processes/statements-documents/delivery-notice.bwp:L14`](../../legacy-bw6/Processes/statements-documents/delivery-notice.bwp#L14) — `"HB.DELIVERY.NOTICE"`.

**Inference (all calls/starters and producer declarations inspected):** every call activityConfig contains only processName, with no input mapping. Each callee also has a JMS starter whose destination has no in-project producer. The [graph](graph.json) suffix matches identify candidates, not proven runtime bindings. Secondary pointer: [spec](specs/payments/instruction-intake.md).

### HTTP side effects, response use and parity coverage

What request body, response mapping and retry/idempotency contract applies, and what HTTP evidence must be captured? Establish and verify the programme-wide contract.

- [`integration/legacy-bw6/Processes/payments/sanctions-screening.bwp:L24`](../../legacy-bw6/Processes/payments/sanctions-screening.bwp#L24) — `"<method>POST</method>"`.
- [`integration/legacy-bw6/Processes/statements-documents/pdf-request.bwp:L24`](../../legacy-bw6/Processes/statements-documents/pdf-request.bwp#L24) — `"<method>POST</method>"`.
- [`integration/legacy-bw6/Processes/statements-documents/document-store.bwp:L24`](../../legacy-bw6/Processes/statements-documents/document-store.bwp#L24) — `"<method>POST</method>"`.
- [`integration/legacy-bw6/Processes/fees-billing/fee-posting.bwp:L24`](../../legacy-bw6/Processes/fees-billing/fee-posting.bwp#L24) — `"<method>POST</method>"`.
- [`integration/legacy-bw6/Processes/customer-alerts/preference-sync.bwp:L24`](../../legacy-bw6/Processes/customer-alerts/preference-sync.bwp#L24) — `"<method>POST</method>"`.
- [`integration/harness/README.md:L152`](../../harness/README.md#L152) — `"messages, rows and files."`.
- [`integration/legacy-bw6/reference/record.py:L77`](../../legacy-bw6/reference/record.py#L77) — `"capture = {"messages": captures"`.
- [`integration/legacy-bw6/reference/record.py:L69`](../../legacy-bw6/reference/record.py#L69) — `"("date", "file", "file-service")"`.

**Inference (all HTTP processes and capture contract inspected):** all five POST before publish; four POST before an insert, while pdf-request has no insert. Their POST configs write DispatchResponse without declaring a request body; the response is not consumed elsewhere. Repeated POSTs may duplicate side effects, but actual service non-idempotence is unverified. The README enumerates messages/rows/files rather than explicitly saying “HTTP is not captured”; the HTTP capture gap is inferred from this contract and recorder construction. Secondary pointer: [spec](specs/payments/sanctions-screening.md).

### Dead-letter ownership and drain contract

Who owns, monitors and drains HB.UNDLV after conversion, including retries and replay authorization? Establish and verify the programme-wide contract.

- [`integration/legacy-bw6/Processes/account-events/account-closed.bwp:L7`](../../legacy-bw6/Processes/account-events/account-closed.bwp#L7) — `"HB.UNDLV"`.
- [`integration/legacy-bw6/Processes/account-events/account-opened.bwp:L7`](../../legacy-bw6/Processes/account-events/account-opened.bwp#L7) — `"HB.UNDLV"`.
- [`integration/legacy-bw6/Processes/account-events/address-changed.bwp:L7`](../../legacy-bw6/Processes/account-events/address-changed.bwp#L7) — `"HB.UNDLV"`.
- [`integration/legacy-bw6/Processes/account-events/event-fanout.bwp:L7`](../../legacy-bw6/Processes/account-events/event-fanout.bwp#L7) — `"HB.UNDLV"`.
- [`integration/legacy-bw6/Processes/account-events/limit-changed.bwp:L7`](../../legacy-bw6/Processes/account-events/limit-changed.bwp#L7) — `"HB.UNDLV"`.
- [`integration/legacy-bw6/Processes/customer-alerts/card-dispute.bwp:L7`](../../legacy-bw6/Processes/customer-alerts/card-dispute.bwp#L7) — `"HB.UNDLV"`.
- [`integration/legacy-bw6/Processes/customer-alerts/large-transaction.bwp:L7`](../../legacy-bw6/Processes/customer-alerts/large-transaction.bwp#L7) — `"HB.UNDLV"`.
- [`integration/legacy-bw6/Processes/customer-alerts/low-balance.bwp:L7`](../../legacy-bw6/Processes/customer-alerts/low-balance.bwp#L7) — `"HB.UNDLV"`.
- [`integration/legacy-bw6/Processes/customer-alerts/preference-sync.bwp:L7`](../../legacy-bw6/Processes/customer-alerts/preference-sync.bwp#L7) — `"HB.UNDLV"`.
- [`integration/legacy-bw6/Processes/fees-billing/daily-fee.bwp:L7`](../../legacy-bw6/Processes/fees-billing/daily-fee.bwp#L7) — `"HB.UNDLV"`.
- [`integration/legacy-bw6/Processes/fees-billing/fee-posting.bwp:L7`](../../legacy-bw6/Processes/fees-billing/fee-posting.bwp#L7) — `"HB.UNDLV"`.
- [`integration/legacy-bw6/Processes/fees-billing/fee-reversal.bwp:L7`](../../legacy-bw6/Processes/fees-billing/fee-reversal.bwp#L7) — `"HB.UNDLV"`.
- [`integration/legacy-bw6/Processes/fees-billing/month-end-summary.bwp:L7`](../../legacy-bw6/Processes/fees-billing/month-end-summary.bwp#L7) — `"HB.UNDLV"`.
- [`integration/legacy-bw6/Processes/payments/currency-routing.bwp:L7`](../../legacy-bw6/Processes/payments/currency-routing.bwp#L7) — `"HB.UNDLV"`.
- [`integration/legacy-bw6/Processes/payments/instruction-intake.bwp:L7`](../../legacy-bw6/Processes/payments/instruction-intake.bwp#L7) — `"HB.UNDLV"`.
- [`integration/legacy-bw6/Processes/payments/payment-returns.bwp:L7`](../../legacy-bw6/Processes/payments/payment-returns.bwp#L7) — `"HB.UNDLV"`.
- [`integration/legacy-bw6/Processes/payments/sanctions-screening.bwp:L7`](../../legacy-bw6/Processes/payments/sanctions-screening.bwp#L7) — `"HB.UNDLV"`.
- [`integration/legacy-bw6/Processes/payments/status-update.bwp:L7`](../../legacy-bw6/Processes/payments/status-update.bwp#L7) — `"HB.UNDLV"`.
- [`integration/legacy-bw6/Processes/payments/validation-enrichment.bwp:L7`](../../legacy-bw6/Processes/payments/validation-enrichment.bwp#L7) — `"HB.UNDLV"`.
- [`integration/legacy-bw6/Processes/statements-documents/delivery-notice.bwp:L7`](../../legacy-bw6/Processes/statements-documents/delivery-notice.bwp#L7) — `"HB.UNDLV"`.
- [`integration/legacy-bw6/Processes/statements-documents/document-store.bwp:L7`](../../legacy-bw6/Processes/statements-documents/document-store.bwp#L7) — `"HB.UNDLV"`.
- [`integration/legacy-bw6/Processes/statements-documents/pdf-request.bwp:L7`](../../legacy-bw6/Processes/statements-documents/pdf-request.bwp#L7) — `"HB.UNDLV"`.
- [`integration/legacy-bw6/Processes/statements-documents/split-enrich.bwp:L7`](../../legacy-bw6/Processes/statements-documents/split-enrich.bwp#L7) — `"HB.UNDLV"`.
- [`integration/legacy-bw6/Processes/statements-documents/statement-drop.bwp:L7`](../../legacy-bw6/Processes/statements-documents/statement-drop.bwp#L7) — `"HB.UNDLV"`.
- [`integration/fixture/broker.xml:L20`](../../fixture/broker.xml#L20) — `"<dead-letter-address>HB.UNDLV</dead-letter-address>"`.
- [`integration/fixture/broker.xml:L21`](../../fixture/broker.xml#L21) — `"<max-delivery-attempts>4</max-delivery-attempts>"`.
- [`integration/fixture/broker.xml:L21`](../../fixture/broker.xml#L21) — `"<redelivery-delay>100</redelivery-delay>"`.
- [`integration/fixture/broker.xml:L26`](../../fixture/broker.xml#L26) — `"<queue name="HB.UNDLV"/>"`.

**Inference (all handlers and starters inspected):** every process names HB.UNDLV as its fault target, but none consumes it. Fixture settings specify four total attempts, while activity maxRedelivery is three, not four retries. Secondary pointer: [spec](specs/account-events/event-fanout.md).

### Durable subscriber and shared client identity

Which durable setting governs the four topic subscribers, and may the target share a broker client identity across all EmsConnection users? Establish and verify the programme-wide contract.

- [`integration/legacy-bw6/SharedResources/EmsConnection.sharedresource:L2`](../../legacy-bw6/SharedResources/EmsConnection.sharedresource#L2) — `"<clientID>halvergate-records</clientID>"`.
- [`integration/legacy-bw6/SharedResources/EmsConnection.sharedresource:L2`](../../legacy-bw6/SharedResources/EmsConnection.sharedresource#L2) — `"<durableSubscription>records-event-fanout</durableSubscription>"`.
- [`integration/legacy-bw6/Processes/account-events/account-opened.bwp:L14`](../../legacy-bw6/Processes/account-events/account-opened.bwp#L14) — `"records-account-opened"`.
- [`integration/legacy-bw6/Processes/account-events/address-changed.bwp:L14`](../../legacy-bw6/Processes/account-events/address-changed.bwp#L14) — `"records-address-changed"`.
- [`integration/legacy-bw6/Processes/account-events/limit-changed.bwp:L14`](../../legacy-bw6/Processes/account-events/limit-changed.bwp#L14) — `"records-limit-changed"`.
- [`integration/legacy-bw6/Processes/account-events/account-closed.bwp:L14`](../../legacy-bw6/Processes/account-events/account-closed.bwp#L14) — `"records-account-closed"`.

**Inference:** precedence and safe concurrent identity reuse are not established by these declarations. The durable-name question directly concerns account-opened, address-changed, limit-changed and account-closed; clientID concerns all EmsConnection users, hence all 24 are listed. Secondary pointer: [spec](specs/account-events/account-opened.md).

### Request schema namespace and validation

Enforce the qualified schema, accept recorded un-namespaced requests, or normalize at ingress? Establish and verify the programme-wide contract.

- [`integration/legacy-bw6/Schemas/request.xsd:L2`](../../legacy-bw6/Schemas/request.xsd#L2) — `"targetNamespace="urn:halvergate:integration:request""`.
- [`integration/legacy-bw6/Schemas/request.xsd:L2`](../../legacy-bw6/Schemas/request.xsd#L2) — `"elementFormDefault="qualified""`.
- [`integration/legacy-bw6/reference/inputs/payments.instruction-intake/instruction-intake-01.xml:L2`](../../legacy-bw6/reference/inputs/payments.instruction-intake/instruction-intake-01.xml#L2) — `"<request id="`.
- [`integration/legacy-bw6/Processes/payments/instruction-intake.bwp:L3`](../../legacy-bw6/Processes/payments/instruction-intake.bwp#L3) — `"../../Schemas/request.xsd"`.

**Inference (recorded root and all imports inspected):** the recorded request root has no namespace; nested Document has an ISO namespace. All processes import request.xsd, but that does not prove runtime validation is enabled. Review unqualified XSLT request matching if namespacing changes. Secondary pointer: [spec](specs/account-events/account-opened.md).


## Wave 1 — Standalone leaf flows

**Straight-conversion lane** (after Wave 0; callees with or before callers):

| Process | Classification | Decision IDs |
| --- | --- | --- |

No straight-conversion processes in this wave.

## Wave 2 — Callees

**Straight-conversion lane** (after Wave 0; callees with or before callers):

| Process | Classification | Decision IDs |
| --- | --- | --- |
| `account-events.account-closed` | straight-conversion | None |
| `account-events.account-opened` | straight-conversion | None |
| `account-events.address-changed` | straight-conversion | None |
| `account-events.limit-changed` | straight-conversion | None |
| `payments.currency-routing` | straight-conversion | None |
| `payments.validation-enrichment` | straight-conversion | None |
| `statements-documents.delivery-notice` | straight-conversion | None |
| `statements-documents.split-enrich` | straight-conversion | None |

## Wave 3 — Callers

**Straight-conversion lane** (after Wave 0; callees with or before callers):

| Process | Classification | Decision IDs |
| --- | --- | --- |

No straight-conversion processes in this wave.

## Held for decision

Target waves reserve ordering only; no held process is released by this plan.

| Process | Classification | Blocking decisions | Target wave |
| --- | --- | --- | --- |
| `account-events.event-fanout` | needs-human-decision | [D-03](decisions.md#d-03-uncalled-or-unfed-entry-flows), [D-07](decisions.md#d-07-event-fanout-queue-versus-durable-topic) | Wave 3 |
| `customer-alerts.card-dispute` | needs-human-decision | [D-03](decisions.md#d-03-uncalled-or-unfed-entry-flows) | Wave 1 |
| `customer-alerts.large-transaction` | needs-human-decision | [D-03](decisions.md#d-03-uncalled-or-unfed-entry-flows) | Wave 1 |
| `customer-alerts.low-balance` | needs-human-decision | [D-03](decisions.md#d-03-uncalled-or-unfed-entry-flows) | Wave 1 |
| `customer-alerts.preference-sync` | needs-human-decision | [D-03](decisions.md#d-03-uncalled-or-unfed-entry-flows) | Wave 1 |
| `fees-billing.daily-fee` | needs-human-decision | [D-03](decisions.md#d-03-uncalled-or-unfed-entry-flows), [D-05](decisions.md#d-05-daily-fee-timer-or-queue-listener), [D-10](decisions.md#d-10-daily-fee-static-rate-cache) | Wave 1 |
| `fees-billing.fee-posting` | needs-human-decision | [D-03](decisions.md#d-03-uncalled-or-unfed-entry-flows) | Wave 1 |
| `fees-billing.fee-reversal` | needs-human-decision | [D-03](decisions.md#d-03-uncalled-or-unfed-entry-flows), [D-11](decisions.md#d-11-fee-reversal-amount-sign) | Wave 1 |
| `fees-billing.month-end-summary` | needs-human-decision | [D-04](decisions.md#d-04-month-end-summary-entry-and-scope) | Wave 1 |
| `payments.instruction-intake` | needs-human-decision | [D-01](decisions.md#d-01-screening-api-version-by-environment), [D-03](decisions.md#d-03-uncalled-or-unfed-entry-flows), [D-08](decisions.md#d-08-payment-status-import-precedence), [D-12](decisions.md#d-12-instruction-intake-xa-scope-ends-before-calls) | Wave 3 |
| `payments.payment-returns` | needs-human-decision | [D-03](decisions.md#d-03-uncalled-or-unfed-entry-flows) | Wave 1 |
| `payments.sanctions-screening` | needs-human-decision | [D-01](decisions.md#d-01-screening-api-version-by-environment), [D-02](decisions.md#d-02-pdf-request-endpoint-ownership) | Wave 2 |
| `payments.status-update` | needs-human-decision | [D-08](decisions.md#d-08-payment-status-import-precedence) | Wave 2 |
| `statements-documents.document-store` | needs-human-decision | [D-09](decisions.md#d-09-document-store-file-side-effect) | Wave 2 |
| `statements-documents.pdf-request` | needs-human-decision | [D-01](decisions.md#d-01-screening-api-version-by-environment), [D-02](decisions.md#d-02-pdf-request-endpoint-ownership) | Wave 2 |
| `statements-documents.statement-drop` | needs-human-decision | [D-01](decisions.md#d-01-screening-api-version-by-environment), [D-03](decisions.md#d-03-uncalled-or-unfed-entry-flows), [D-06](decisions.md#d-06-statement-drop-transport-and-file-rejection) | Wave 3 |

## Wave summary

- **Wave 1:** 0 straight conversions; 9 held.
- **Wave 2:** 8 straight conversions; 4 held.
- **Wave 3:** 0 straight conversions; 3 held.
