# BW6 conversion decisions

Decisions a person must make before a flow reaches the conversion plan. **Nothing here is decided.** Run **tib-d1111**. Citations use the specs’ repo-root `path:L<n>` format, linked relative to this file. **Inference** labels mark conclusions from inspection, absence searches, counts or language semantics rather than directly quoted declarations. Options are neutral possibilities, not recommendations.

## D-01 Screening API version by environment

**Affected processes:** `payments.sanctions-screening`, `statements-documents.pdf-request`, `payments.instruction-intake`, `statements-documents.statement-drop`.

**Question:** Which screening version belongs in each environment?

**Evidence**

- [`integration/legacy-bw6/Profiles/dev.substvar:L2`](../../legacy-bw6/Profiles/dev.substvar#L2) — `"http://screening:8080/v1/screen"`.
- [`integration/legacy-bw6/Profiles/prod.substvar:L2`](../../legacy-bw6/Profiles/prod.substvar#L2) — `"http://screening:8080/v2/screen"`.
- [`integration/legacy-bw6/Processes/payments/sanctions-screening.bwp:L24`](../../legacy-bw6/Processes/payments/sanctions-screening.bwp#L24) — `"${screening.url}"`.
- [`integration/legacy-bw6/Processes/statements-documents/pdf-request.bwp:L24`](../../legacy-bw6/Processes/statements-documents/pdf-request.bwp#L24) — `"${screening.url}"`.
- [`integration/legacy-bw6/Processes/payments/instruction-intake.bwp:L48`](../../legacy-bw6/Processes/payments/instruction-intake.bwp#L48) — `"payments.sanctions-screening"`.
- [`integration/legacy-bw6/Processes/statements-documents/statement-drop.bwp:L44`](../../legacy-bw6/Processes/statements-documents/statement-drop.bwp#L44) — `"statements-documents.pdf-request"`.
- [`integration/legacy-bw6/Profiles/dev.substvar:L2`](../../legacy-bw6/Profiles/dev.substvar#L2) — `"http://billing-service:8092/api/fees"`.
- [`integration/legacy-bw6/Profiles/dev.substvar:L2`](../../legacy-bw6/Profiles/dev.substvar#L2) — `"http://file-service:8082/api/files"`.
- [`integration/legacy-bw6/Profiles/dev.substvar:L2`](../../legacy-bw6/Profiles/dev.substvar#L2) — `"http://notification-service:8086/api/notifications"`.
- [`integration/legacy-bw6/Profiles/prod.substvar:L2`](../../legacy-bw6/Profiles/prod.substvar#L2) — `"http://billing-service:8092/api/fees"`.
- [`integration/legacy-bw6/Profiles/prod.substvar:L2`](../../legacy-bw6/Profiles/prod.substvar#L2) — `"http://file-service:8082/api/files"`.
- [`integration/legacy-bw6/Profiles/prod.substvar:L2`](../../legacy-bw6/Profiles/prod.substvar#L2) — `"http://notification-service:8086/api/notifications"`.

**Inference:** instruction-intake and statement-drop are indirectly affected if their call references resolve (D-04). billing.url, files.url and notifications.url have identical values in both profiles. Secondary pointer: [spec](specs/payments/sanctions-screening.md).

**Options**

A. Keep dev v1 and prod v2.
B. Use one approved version in both environments.
C. Define version-specific routes with environment mappings.

**Decision:** 

## D-02 PDF request endpoint ownership

**Affected processes:** `statements-documents.pdf-request`, `payments.sanctions-screening`.

**Question:** Is the shared screening endpoint intentional for PDF requests, or should the property and endpoint be split?

**Evidence**

- [`integration/legacy-bw6/Processes/statements-documents/pdf-request.bwp:L24`](../../legacy-bw6/Processes/statements-documents/pdf-request.bwp#L24) — `"${screening.url}"`.
- [`integration/legacy-bw6/Processes/payments/sanctions-screening.bwp:L24`](../../legacy-bw6/Processes/payments/sanctions-screening.bwp#L24) — `"${screening.url}"`.

Secondary pointer: [spec](specs/statements-documents/pdf-request.md).

**Options**

A. Keep one shared property and endpoint.
B. Split properties but keep their current values.
C. Supply an independently approved PDF endpoint.

**Decision:** 

## D-03 Environment credentials and literal hosts

**Affected processes:** `account-events.account-closed`, `account-events.account-opened`, `account-events.address-changed`, `account-events.event-fanout`, `account-events.limit-changed`, `customer-alerts.card-dispute`, `customer-alerts.large-transaction`, `customer-alerts.low-balance`, `customer-alerts.preference-sync`, `fees-billing.daily-fee`, `fees-billing.fee-posting`, `fees-billing.fee-reversal`, `fees-billing.month-end-summary`, `payments.currency-routing`, `payments.instruction-intake`, `payments.payment-returns`, `payments.sanctions-screening`, `payments.status-update`, `payments.validation-enrichment`, `statements-documents.delivery-notice`, `statements-documents.document-store`, `statements-documents.pdf-request`, `statements-documents.split-enrich`, `statements-documents.statement-drop`.

**Question:** Where do per-environment credentials and host values come from? SFTP credentials apply only to statement-drop and split-enrich.

**Evidence**

- [`integration/legacy-bw6/SharedResources/EmsConnection.sharedresource:L2`](../../legacy-bw6/SharedResources/EmsConnection.sharedresource#L2) — `"${EMS_USER}"`.
- [`integration/legacy-bw6/SharedResources/EmsConnection.sharedresource:L2`](../../legacy-bw6/SharedResources/EmsConnection.sharedresource#L2) — `"${EMS_PASSWORD}"`.
- [`integration/legacy-bw6/SharedResources/EmsConnection.sharedresource:L2`](../../legacy-bw6/SharedResources/EmsConnection.sharedresource#L2) — `"tcp://broker:61616"`.
- [`integration/legacy-bw6/SharedResources/LedgerJdbc.sharedresource:L2`](../../legacy-bw6/SharedResources/LedgerJdbc.sharedresource#L2) — `"${DB_USER}"`.
- [`integration/legacy-bw6/SharedResources/LedgerJdbc.sharedresource:L2`](../../legacy-bw6/SharedResources/LedgerJdbc.sharedresource#L2) — `"${DB_PASSWORD}"`.
- [`integration/legacy-bw6/SharedResources/LedgerJdbc.sharedresource:L2`](../../legacy-bw6/SharedResources/LedgerJdbc.sharedresource#L2) — `"jdbc:postgresql://integration-db:5432/integration"`.
- [`integration/legacy-bw6/SharedResources/StatementSftp.sharedresource:L2`](../../legacy-bw6/SharedResources/StatementSftp.sharedresource#L2) — `"${SFTP_USER}"`.
- [`integration/legacy-bw6/SharedResources/StatementSftp.sharedresource:L2`](../../legacy-bw6/SharedResources/StatementSftp.sharedresource#L2) — `"${SFTP_PASSWORD}"`.
- [`integration/legacy-bw6/SharedResources/StatementSftp.sharedresource:L2`](../../legacy-bw6/SharedResources/StatementSftp.sharedresource#L2) — `"<host>sftp</host>"`.
- [`integration/legacy-bw6/Profiles/dev.substvar:L2`](../../legacy-bw6/Profiles/dev.substvar#L2) — `"<globalVariables>"`.
- [`integration/legacy-bw6/Profiles/prod.substvar:L2`](../../legacy-bw6/Profiles/prod.substvar#L2) — `"<globalVariables>"`.

**Inference (complete profiles and activities inspected):** neither profile defines these six credential variables; broker, database and SFTP hosts are literal strings, not profile variables. All flows use EMS credentials. JDBC credentials apply to the 22 JDBC flows, not currency-routing or pdf-request. Only statement-drop and split-enrich use SFTP. Secondary pointer: [spec](specs/statements-documents/statement-drop.md).

**Options**

A. Keep placeholders with a documented external secret/environment provider.
B. Define explicit per-environment secret and host mappings.
C. Retain literal hosts behind environment-specific service discovery.

**Decision:** 

## D-04 Call-process binding and independent starters

**Affected processes:** `account-events.event-fanout`, `account-events.account-opened`, `account-events.address-changed`, `account-events.limit-changed`, `account-events.account-closed`, `payments.instruction-intake`, `payments.validation-enrichment`, `payments.sanctions-screening`, `payments.currency-routing`, `payments.status-update`, `statements-documents.statement-drop`, `statements-documents.split-enrich`, `statements-documents.pdf-request`, `statements-documents.document-store`, `statements-documents.delivery-notice`.

**Question:** Do unprefixed names resolve? Should callees be in-process subprocesses, independent queue/topic consumers, or both, and what input mapping applies?

**Evidence**

- [`integration/legacy-bw6/Processes/account-events/event-fanout.bwp:L34`](../../legacy-bw6/Processes/account-events/event-fanout.bwp#L34) — `"account-events.account-opened"`.
- [`integration/legacy-bw6/Processes/account-events/account-opened.bwp:L2`](../../legacy-bw6/Processes/account-events/account-opened.bwp#L2) — `"halvergate.account-events.account-opened"`.
- [`integration/legacy-bw6/Processes/account-events/account-opened.bwp:L14`](../../legacy-bw6/Processes/account-events/account-opened.bwp#L14) — `"<destination>"`.
- [`integration/legacy-bw6/Processes/account-events/event-fanout.bwp:L39`](../../legacy-bw6/Processes/account-events/event-fanout.bwp#L39) — `"account-events.address-changed"`.
- [`integration/legacy-bw6/Processes/account-events/address-changed.bwp:L2`](../../legacy-bw6/Processes/account-events/address-changed.bwp#L2) — `"halvergate.account-events.address-changed"`.
- [`integration/legacy-bw6/Processes/account-events/address-changed.bwp:L14`](../../legacy-bw6/Processes/account-events/address-changed.bwp#L14) — `"<destination>"`.
- [`integration/legacy-bw6/Processes/account-events/event-fanout.bwp:L44`](../../legacy-bw6/Processes/account-events/event-fanout.bwp#L44) — `"account-events.limit-changed"`.
- [`integration/legacy-bw6/Processes/account-events/limit-changed.bwp:L2`](../../legacy-bw6/Processes/account-events/limit-changed.bwp#L2) — `"halvergate.account-events.limit-changed"`.
- [`integration/legacy-bw6/Processes/account-events/limit-changed.bwp:L14`](../../legacy-bw6/Processes/account-events/limit-changed.bwp#L14) — `"<destination>"`.
- [`integration/legacy-bw6/Processes/account-events/event-fanout.bwp:L49`](../../legacy-bw6/Processes/account-events/event-fanout.bwp#L49) — `"account-events.account-closed"`.
- [`integration/legacy-bw6/Processes/account-events/account-closed.bwp:L2`](../../legacy-bw6/Processes/account-events/account-closed.bwp#L2) — `"halvergate.account-events.account-closed"`.
- [`integration/legacy-bw6/Processes/account-events/account-closed.bwp:L14`](../../legacy-bw6/Processes/account-events/account-closed.bwp#L14) — `"<destination>"`.
- [`integration/legacy-bw6/Processes/payments/instruction-intake.bwp:L43`](../../legacy-bw6/Processes/payments/instruction-intake.bwp#L43) — `"payments.validation-enrichment"`.
- [`integration/legacy-bw6/Processes/payments/validation-enrichment.bwp:L2`](../../legacy-bw6/Processes/payments/validation-enrichment.bwp#L2) — `"halvergate.payments.validation-enrichment"`.
- [`integration/legacy-bw6/Processes/payments/validation-enrichment.bwp:L14`](../../legacy-bw6/Processes/payments/validation-enrichment.bwp#L14) — `"<destination>"`.
- [`integration/legacy-bw6/Processes/payments/instruction-intake.bwp:L48`](../../legacy-bw6/Processes/payments/instruction-intake.bwp#L48) — `"payments.sanctions-screening"`.
- [`integration/legacy-bw6/Processes/payments/sanctions-screening.bwp:L2`](../../legacy-bw6/Processes/payments/sanctions-screening.bwp#L2) — `"halvergate.payments.sanctions-screening"`.
- [`integration/legacy-bw6/Processes/payments/sanctions-screening.bwp:L14`](../../legacy-bw6/Processes/payments/sanctions-screening.bwp#L14) — `"<destination>"`.
- [`integration/legacy-bw6/Processes/payments/instruction-intake.bwp:L53`](../../legacy-bw6/Processes/payments/instruction-intake.bwp#L53) — `"payments.currency-routing"`.
- [`integration/legacy-bw6/Processes/payments/currency-routing.bwp:L2`](../../legacy-bw6/Processes/payments/currency-routing.bwp#L2) — `"halvergate.payments.currency-routing"`.
- [`integration/legacy-bw6/Processes/payments/currency-routing.bwp:L14`](../../legacy-bw6/Processes/payments/currency-routing.bwp#L14) — `"<destination>"`.
- [`integration/legacy-bw6/Processes/payments/instruction-intake.bwp:L58`](../../legacy-bw6/Processes/payments/instruction-intake.bwp#L58) — `"payments.status-update"`.
- [`integration/legacy-bw6/Processes/payments/status-update.bwp:L2`](../../legacy-bw6/Processes/payments/status-update.bwp#L2) — `"halvergate.payments.status-update"`.
- [`integration/legacy-bw6/Processes/payments/status-update.bwp:L14`](../../legacy-bw6/Processes/payments/status-update.bwp#L14) — `"<destination>"`.
- [`integration/legacy-bw6/Processes/statements-documents/statement-drop.bwp:L39`](../../legacy-bw6/Processes/statements-documents/statement-drop.bwp#L39) — `"statements-documents.split-enrich"`.
- [`integration/legacy-bw6/Processes/statements-documents/split-enrich.bwp:L2`](../../legacy-bw6/Processes/statements-documents/split-enrich.bwp#L2) — `"halvergate.statements-documents.split-enrich"`.
- [`integration/legacy-bw6/Processes/statements-documents/split-enrich.bwp:L14`](../../legacy-bw6/Processes/statements-documents/split-enrich.bwp#L14) — `"<destination>"`.
- [`integration/legacy-bw6/Processes/statements-documents/statement-drop.bwp:L44`](../../legacy-bw6/Processes/statements-documents/statement-drop.bwp#L44) — `"statements-documents.pdf-request"`.
- [`integration/legacy-bw6/Processes/statements-documents/pdf-request.bwp:L2`](../../legacy-bw6/Processes/statements-documents/pdf-request.bwp#L2) — `"halvergate.statements-documents.pdf-request"`.
- [`integration/legacy-bw6/Processes/statements-documents/pdf-request.bwp:L14`](../../legacy-bw6/Processes/statements-documents/pdf-request.bwp#L14) — `"<destination>"`.
- [`integration/legacy-bw6/Processes/statements-documents/statement-drop.bwp:L49`](../../legacy-bw6/Processes/statements-documents/statement-drop.bwp#L49) — `"statements-documents.document-store"`.
- [`integration/legacy-bw6/Processes/statements-documents/document-store.bwp:L2`](../../legacy-bw6/Processes/statements-documents/document-store.bwp#L2) — `"halvergate.statements-documents.document-store"`.
- [`integration/legacy-bw6/Processes/statements-documents/document-store.bwp:L14`](../../legacy-bw6/Processes/statements-documents/document-store.bwp#L14) — `"<destination>"`.
- [`integration/legacy-bw6/Processes/statements-documents/statement-drop.bwp:L54`](../../legacy-bw6/Processes/statements-documents/statement-drop.bwp#L54) — `"statements-documents.delivery-notice"`.
- [`integration/legacy-bw6/Processes/statements-documents/delivery-notice.bwp:L2`](../../legacy-bw6/Processes/statements-documents/delivery-notice.bwp#L2) — `"halvergate.statements-documents.delivery-notice"`.
- [`integration/legacy-bw6/Processes/statements-documents/delivery-notice.bwp:L14`](../../legacy-bw6/Processes/statements-documents/delivery-notice.bwp#L14) — `"<destination>"`.

**Inference (all calls/starters and producer declarations inspected):** every call activityConfig contains only processName, with no input mapping. Each callee also has a JMS starter whose destination has no in-project producer. The [graph](graph.json) suffix matches identify candidates, not proven runtime bindings. Secondary pointer: [spec](specs/payments/instruction-intake.md).

**Options**

A. Preserve configured names and both entry paths subject to verified BW resolution.
B. Resolve names explicitly and use subprocesses with defined inputs.
C. Keep independent JMS consumers and replace calls with approved messaging.
D. Keep both entry paths with explicit input and deduplication contracts.

**Decision:** 

## D-05 External entry producers and output consumers

**Affected processes:** `account-events.event-fanout`, `customer-alerts.card-dispute`, `customer-alerts.large-transaction`, `customer-alerts.low-balance`, `customer-alerts.preference-sync`, `fees-billing.daily-fee`, `fees-billing.fee-posting`, `fees-billing.fee-reversal`, `payments.instruction-intake`, `payments.payment-returns`, `statements-documents.statement-drop`.

**Question:** Confirm an external producer for each entry below or approve retirement; confirm external consumers for all 25 listed destinations. Month-end-summary is excluded from the entry list (D-06).

**Evidence**

- [`integration/legacy-bw6/Processes/account-events/event-fanout.bwp:L14`](../../legacy-bw6/Processes/account-events/event-fanout.bwp#L14) — `"HB.ACCOUNT.EVENTS.IN"`.
- [`integration/legacy-bw6/Processes/customer-alerts/card-dispute.bwp:L14`](../../legacy-bw6/Processes/customer-alerts/card-dispute.bwp#L14) — `"HB.ALERTS.CARD.DISPUTE"`.
- [`integration/legacy-bw6/Processes/customer-alerts/large-transaction.bwp:L14`](../../legacy-bw6/Processes/customer-alerts/large-transaction.bwp#L14) — `"HB.ALERTS.LARGE.TRANSACTION"`.
- [`integration/legacy-bw6/Processes/customer-alerts/low-balance.bwp:L14`](../../legacy-bw6/Processes/customer-alerts/low-balance.bwp#L14) — `"HB.ALERTS.LOW.BALANCE"`.
- [`integration/legacy-bw6/Processes/customer-alerts/preference-sync.bwp:L14`](../../legacy-bw6/Processes/customer-alerts/preference-sync.bwp#L14) — `"HB.ALERT.PREFERENCES"`.
- [`integration/legacy-bw6/Processes/fees-billing/daily-fee.bwp:L14`](../../legacy-bw6/Processes/fees-billing/daily-fee.bwp#L14) — `"HB.DAILY.FEES"`.
- [`integration/legacy-bw6/Processes/fees-billing/fee-posting.bwp:L14`](../../legacy-bw6/Processes/fees-billing/fee-posting.bwp#L14) — `"HB.FEE.POSTING"`.
- [`integration/legacy-bw6/Processes/fees-billing/fee-reversal.bwp:L14`](../../legacy-bw6/Processes/fees-billing/fee-reversal.bwp#L14) — `"HB.FEE.REVERSAL"`.
- [`integration/legacy-bw6/Processes/payments/instruction-intake.bwp:L16`](../../legacy-bw6/Processes/payments/instruction-intake.bwp#L16) — `"HB.PAYMENT.INSTRUCTIONS"`.
- [`integration/legacy-bw6/Processes/payments/payment-returns.bwp:L14`](../../legacy-bw6/Processes/payments/payment-returns.bwp#L14) — `"HB.PAYMENT.RETURNS"`.
- [`integration/legacy-bw6/Processes/statements-documents/statement-drop.bwp:L14`](../../legacy-bw6/Processes/statements-documents/statement-drop.bwp#L14) — `"HB.STATEMENT.DROP"`.
- [`integration/legacy-bw6/SharedResources/EmsConnection.sharedresource:L2`](../../legacy-bw6/SharedResources/EmsConnection.sharedresource#L2) — `"HB.UNDLV"`.

**Inference (source-derived [graph summary](graph.json)):** 12 processes have neither an incoming call nor an in-project starter producer. Excluding month-end-summary leaves 11 entry candidates: `account-events.event-fanout`, `customer-alerts.card-dispute`, `customer-alerts.large-transaction`, `customer-alerts.low-balance`, `customer-alerts.preference-sync`, `fees-billing.daily-fee`, `fees-billing.fee-posting`, `fees-billing.fee-reversal`, `payments.instruction-intake`, `payments.payment-returns`, `statements-documents.statement-drop`. All 24 processes are affected by output/dead-letter ownership. The 25 destinations with no in-project consumer are: `HB.ACCOUNT.ARCHIVED`, `HB.ACCOUNT.CREATED`, `HB.ACCOUNT.EVENTS`, `HB.ADDRESS.UPDATED`, `HB.CURRENCY.ROUTED`, `HB.DELIVERY.CONFIRMED`, `HB.DISPUTE.RECEIVED`, `HB.DOCUMENT.STORED`, `HB.FEE.CALCULATED`, `HB.FEE.POSTED`, `HB.FEE.REVERSED`, `HB.FEE.SUMMARY`, `HB.LARGE.TRANSACTION.ALERTED`, `HB.LIMIT.UPDATED`, `HB.LOW.BALANCE.ALERTED`, `HB.PAYMENT.ENRICHED`, `HB.PAYMENT.STATUS`, `HB.PDF.REQUESTED`, `HB.PREFERENCES.SYNCED`, `HB.RETURN.POSTED`, `HB.SANCTIONS.RESPONSE`, `HB.STATEMENT.ENRICHED`, `HB.STATEMENT.READY`, `HB.STATUS.PUBLISHED`, `HB.UNDLV`. Absence from this export does not prove absence in the deployed estate. Secondary pointer: [spec](specs/customer-alerts/card-dispute.md).

**Options**

A. Document external producers/consumers and keep confirmed flows.
B. Retire individually confirmed unused flows or destinations.
C. Add explicitly owned paths for confirmed missing dependencies.

**Decision:** 

## D-06 Month-end-summary entry and scope

**Affected processes:** `fees-billing.month-end-summary`.

**Question:** Is the flow dead, externally invoked, or intended to become a scheduled job?

**Evidence**

- [`integration/legacy-bw6/Processes/fees-billing/month-end-summary.bwp:L14`](../../legacy-bw6/Processes/fees-billing/month-end-summary.bwp#L14) — `"bw.internal.start"`.
- [`integration/legacy-bw6/Processes/fees-billing/month-end-summary.bwp:L14`](../../legacy-bw6/Processes/fees-billing/month-end-summary.bwp#L14) — `"HB.MONTH.END.SUMMARY"`.

**Inference (all processName references inspected):** no in-project caller targets this process. An internal.start destination field does not prove queue consumption. Secondary pointer: [spec](specs/fees-billing/month-end-summary.md).

**Options**

A. Keep an explicitly documented external invocation.
B. Use an approved scheduled job.
C. Retire after confirming no external use.

**Decision:** 

## D-07 Daily-fee timer or queue listener

**Affected processes:** `fees-billing.daily-fee`.

**Question:** Is this a timer or queue listener, and what schedule or producer contract applies?

**Evidence**

- [`integration/legacy-bw6/Processes/fees-billing/daily-fee.bwp:L14`](../../legacy-bw6/Processes/fees-billing/daily-fee.bwp#L14) — `"bw.jms.Timer"`.
- [`integration/legacy-bw6/Processes/fees-billing/daily-fee.bwp:L14`](../../legacy-bw6/Processes/fees-billing/daily-fee.bwp#L14) — `"HB.DAILY.FEES"`.
- [`integration/legacy-bw6/Processes/fees-billing/daily-fee.bwp:L14`](../../legacy-bw6/Processes/fees-billing/daily-fee.bwp#L14) — `"CLIENT_ACKNOWLEDGE"`.

**Inference (complete starter configuration inspected):** no schedule is declared; destination/acknowledgement fields do not establish timer runtime behavior. Secondary pointer: [spec](specs/fees-billing/daily-fee.md).

**Options**

A. Define a timer schedule and payload source.
B. Use a queue listener with an identified producer.
C. Support separately defined timer and queue entries.

**Decision:** 

## D-08 Statement-drop transport and file rejection

**Affected processes:** `statements-documents.statement-drop`.

**Question:** SFTP poller, queue consumer, or both? What does reject/redeliver mean for a file and its partial side effects?

**Evidence**

- [`integration/legacy-bw6/Processes/statements-documents/statement-drop.bwp:L14`](../../legacy-bw6/Processes/statements-documents/statement-drop.bwp#L14) — `"bw.sftp.SFTPGet"`.
- [`integration/legacy-bw6/Processes/statements-documents/statement-drop.bwp:L14`](../../legacy-bw6/Processes/statements-documents/statement-drop.bwp#L14) — `"HB.STATEMENT.DROP"`.
- [`integration/legacy-bw6/Processes/statements-documents/statement-drop.bwp:L14`](../../legacy-bw6/Processes/statements-documents/statement-drop.bwp#L14) — `"CLIENT_ACKNOWLEDGE"`.
- [`integration/legacy-bw6/Processes/statements-documents/statement-drop.bwp:L14`](../../legacy-bw6/Processes/statements-documents/statement-drop.bwp#L14) — `"<durableSubscriber></durableSubscriber>"`.
- [`integration/legacy-bw6/Processes/statements-documents/statement-drop.bwp:L7`](../../legacy-bw6/Processes/statements-documents/statement-drop.bwp#L7) — `"<acknowledge>false</acknowledge>"`.
- [`integration/legacy-bw6/SharedResources/StatementSftp.sharedresource:L2`](../../legacy-bw6/SharedResources/StatementSftp.sharedresource#L2) — `"<remoteDirectory>/upload/in</remoteDirectory>"`.

**Inference:** SFTPGet carries JMS-oriented fields, including an empty durableSubscriber, alongside a JMS rejection handler; the declarations do not define file retry semantics. Secondary pointer: [spec](specs/statements-documents/statement-drop.md).

**Options**

A. Use an SFTP poller with defined pickup, completion, retry and quarantine rules.
B. Use a JMS consumer with a file-reference payload.
C. Keep separate SFTP/JMS entries sharing an explicit processing contract.

**Decision:** 

## D-09 Transaction and acknowledgement boundary

**Affected processes:** `account-events.account-closed`, `account-events.account-opened`, `account-events.address-changed`, `account-events.event-fanout`, `account-events.limit-changed`, `customer-alerts.card-dispute`, `customer-alerts.large-transaction`, `customer-alerts.low-balance`, `customer-alerts.preference-sync`, `fees-billing.daily-fee`, `fees-billing.fee-posting`, `fees-billing.fee-reversal`, `fees-billing.month-end-summary`, `payments.currency-routing`, `payments.instruction-intake`, `payments.payment-returns`, `payments.sanctions-screening`, `payments.status-update`, `payments.validation-enrichment`, `statements-documents.delivery-notice`, `statements-documents.document-store`, `statements-documents.pdf-request`, `statements-documents.split-enrich`, `statements-documents.statement-drop`.

**Question:** Which persistence/publish/ack boundary and duplicate-delivery behavior must conversion preserve or change?

**Evidence**

- [`integration/legacy-bw6/Processes/payments/instruction-intake.bwp:L12`](../../legacy-bw6/Processes/payments/instruction-intake.bwp#L12) — `"transactionType="XA""`.
- [`integration/legacy-bw6/Processes/payments/instruction-intake.bwp:L26`](../../legacy-bw6/Processes/payments/instruction-intake.bwp#L26) — `"TRANSACTION_GROUP"`.
- [`integration/legacy-bw6/Processes/payments/instruction-intake.bwp:L31`](../../legacy-bw6/Processes/payments/instruction-intake.bwp#L31) — `"TRANSACTION_GROUP"`.
- [`integration/legacy-bw6/Processes/payments/instruction-intake.bwp:L40`](../../legacy-bw6/Processes/payments/instruction-intake.bwp#L40) — `"</bpws:scope>"`.
- [`integration/legacy-bw6/Processes/payments/instruction-intake.bwp:L43`](../../legacy-bw6/Processes/payments/instruction-intake.bwp#L43) — `"payments.validation-enrichment"`.
- [`integration/legacy-bw6/Processes/payments/instruction-intake.bwp:L48`](../../legacy-bw6/Processes/payments/instruction-intake.bwp#L48) — `"payments.sanctions-screening"`.
- [`integration/legacy-bw6/Processes/payments/instruction-intake.bwp:L53`](../../legacy-bw6/Processes/payments/instruction-intake.bwp#L53) — `"payments.currency-routing"`.
- [`integration/legacy-bw6/Processes/payments/instruction-intake.bwp:L58`](../../legacy-bw6/Processes/payments/instruction-intake.bwp#L58) — `"payments.status-update"`.
- [`integration/legacy-bw6/Processes/account-events/account-opened.bwp:L24`](../../legacy-bw6/Processes/account-events/account-opened.bwp#L24) — `"AUTO_COMMIT"`.
- [`integration/legacy-bw6/Processes/account-events/account-opened.bwp:L29`](../../legacy-bw6/Processes/account-events/account-opened.bwp#L29) — `"bw.jms.JMSSendMessage"`.
- [`integration/legacy-bw6/Processes/account-events/account-opened.bwp:L7`](../../legacy-bw6/Processes/account-events/account-opened.bwp#L7) — `"<maxRedelivery>3</maxRedelivery>"`.
- [`integration/legacy-bw6/Processes/account-events/account-opened.bwp:L14`](../../legacy-bw6/Processes/account-events/account-opened.bwp#L14) — `"CLIENT_ACKNOWLEDGE"`.
- [`integration/legacy-bw6/SharedResources/LedgerJdbc.sharedresource:L2`](../../legacy-bw6/SharedResources/LedgerJdbc.sharedresource#L2) — `"<transactionType>XA</transactionType>"`.
- [`integration/legacy-bw6/Database/schema.sql:L8`](../../legacy-bw6/Database/schema.sql#L8) — `"PRIMARY KEY (flow, request_id)"`.
- [`integration/legacy-bw6/Processes/payments/currency-routing.bwp:L22`](../../legacy-bw6/Processes/payments/currency-routing.bwp#L22) — `"RouteCurrency"`.
- [`integration/legacy-bw6/Processes/statements-documents/pdf-request.bwp:L24`](../../legacy-bw6/Processes/statements-documents/pdf-request.bwp#L24) — `"bw.http.SendHTTPRequest"`.
- [`integration/legacy-bw6/Processes/statements-documents/pdf-request.bwp:L29`](../../legacy-bw6/Processes/statements-documents/pdf-request.bwp#L29) — `"bw.jms.JMSSendMessage"`.

**Inference (complete processes/schema inspected):** not 23 AUTO_COMMIT processes: there are 23 JDBCUpdate activities in 22 processes. Twenty-one processes each have one AUTO_COMMIT update; instruction-intake has two TRANSACTION_GROUP updates inside XA. Currency-routing and pdf-request have no JDBC activity. The other 23 processes have no transaction scope. All 24 have only a fault-path negative JMSConfirm, with no declared success-path JMSConfirm. All tables have a (flow, request_id) primary key. A committed insert followed by failure can collide on retry and exhaust configured redelivery into HB.UNDLV; this is an inferred failure path, not demonstrated BW execution. All four instruction-intake calls run after the scope closes. Secondary pointer: [spec](specs/payments/instruction-intake.md).

**Options**

A. Preserve declared modes and ordering as-is.
B. Use a local transaction and a defined acknowledgement point.
C. Use an XA scope for agreed resources.
D. Use an outbox for persistence-to-message handoff.
E. Use idempotent inserts/deduplication with an agreed publish/ack policy.

**Decision:** 

## D-10 HTTP side effects, response use and parity coverage

**Affected processes:** `payments.sanctions-screening`, `statements-documents.pdf-request`, `statements-documents.document-store`, `fees-billing.fee-posting`, `customer-alerts.preference-sync`.

**Question:** What request body, response mapping and retry/idempotency contract applies, and what HTTP evidence must be captured?

**Evidence**

- [`integration/legacy-bw6/Processes/payments/sanctions-screening.bwp:L24`](../../legacy-bw6/Processes/payments/sanctions-screening.bwp#L24) — `"<method>POST</method>"`.
- [`integration/legacy-bw6/Processes/statements-documents/pdf-request.bwp:L24`](../../legacy-bw6/Processes/statements-documents/pdf-request.bwp#L24) — `"<method>POST</method>"`.
- [`integration/legacy-bw6/Processes/statements-documents/document-store.bwp:L24`](../../legacy-bw6/Processes/statements-documents/document-store.bwp#L24) — `"<method>POST</method>"`.
- [`integration/legacy-bw6/Processes/fees-billing/fee-posting.bwp:L24`](../../legacy-bw6/Processes/fees-billing/fee-posting.bwp#L24) — `"<method>POST</method>"`.
- [`integration/legacy-bw6/Processes/customer-alerts/preference-sync.bwp:L24`](../../legacy-bw6/Processes/customer-alerts/preference-sync.bwp#L24) — `"<method>POST</method>"`.
- [`integration/harness/README.md:L152`](../../harness/README.md#L152) — `"messages, rows and files."`.
- [`integration/legacy-bw6/reference/record.py:L77`](../../legacy-bw6/reference/record.py#L77) — `"capture = {"messages": captures"`.
- [`integration/legacy-bw6/reference/record.py:L69`](../../legacy-bw6/reference/record.py#L69) — `"("date", "file", "file-service")"`.

**Inference (all HTTP processes and capture contract inspected):** all five POST before publish; four POST before an insert, while pdf-request has no insert. Their POST configs write DispatchResponse without declaring a request body; the response is not consumed elsewhere. Repeated POSTs may duplicate side effects, but actual service non-idempotence is unverified. The README enumerates messages/rows/files rather than explicitly saying “HTTP is not captured”; the HTTP capture gap is inferred from this contract and recorder construction. Secondary pointer: [spec](specs/payments/sanctions-screening.md).

**Options**

A. Keep declared ordering and document unresolved request/response contracts.
B. Define body/response mappings and service-supported idempotency keys.
C. Use approved asynchronous dispatch and add HTTP parity evidence.

**Decision:** 

## D-11 Dead-letter ownership and drain contract

**Affected processes:** `account-events.account-closed`, `account-events.account-opened`, `account-events.address-changed`, `account-events.event-fanout`, `account-events.limit-changed`, `customer-alerts.card-dispute`, `customer-alerts.large-transaction`, `customer-alerts.low-balance`, `customer-alerts.preference-sync`, `fees-billing.daily-fee`, `fees-billing.fee-posting`, `fees-billing.fee-reversal`, `fees-billing.month-end-summary`, `payments.currency-routing`, `payments.instruction-intake`, `payments.payment-returns`, `payments.sanctions-screening`, `payments.status-update`, `payments.validation-enrichment`, `statements-documents.delivery-notice`, `statements-documents.document-store`, `statements-documents.pdf-request`, `statements-documents.split-enrich`, `statements-documents.statement-drop`.

**Question:** Who owns, monitors and drains HB.UNDLV after conversion, including retries and replay authorization?

**Evidence**

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

**Options**

A. Keep a broker-managed DLQ and separately owned drain/replay service.
B. Assign a target-platform dead-letter workflow and operator ownership.
C. Quarantine for manual review without automatic replay.

**Decision:** 

## D-12 Durable subscriber and shared client identity

**Affected processes:** `account-events.account-closed`, `account-events.account-opened`, `account-events.address-changed`, `account-events.event-fanout`, `account-events.limit-changed`, `customer-alerts.card-dispute`, `customer-alerts.large-transaction`, `customer-alerts.low-balance`, `customer-alerts.preference-sync`, `fees-billing.daily-fee`, `fees-billing.fee-posting`, `fees-billing.fee-reversal`, `fees-billing.month-end-summary`, `payments.currency-routing`, `payments.instruction-intake`, `payments.payment-returns`, `payments.sanctions-screening`, `payments.status-update`, `payments.validation-enrichment`, `statements-documents.delivery-notice`, `statements-documents.document-store`, `statements-documents.pdf-request`, `statements-documents.split-enrich`, `statements-documents.statement-drop`.

**Question:** Which durable setting governs the four topic subscribers, and may the target share a broker client identity across all EmsConnection users?

**Evidence**

- [`integration/legacy-bw6/SharedResources/EmsConnection.sharedresource:L2`](../../legacy-bw6/SharedResources/EmsConnection.sharedresource#L2) — `"<clientID>halvergate-records</clientID>"`.
- [`integration/legacy-bw6/SharedResources/EmsConnection.sharedresource:L2`](../../legacy-bw6/SharedResources/EmsConnection.sharedresource#L2) — `"<durableSubscription>records-event-fanout</durableSubscription>"`.
- [`integration/legacy-bw6/Processes/account-events/account-opened.bwp:L14`](../../legacy-bw6/Processes/account-events/account-opened.bwp#L14) — `"records-account-opened"`.
- [`integration/legacy-bw6/Processes/account-events/address-changed.bwp:L14`](../../legacy-bw6/Processes/account-events/address-changed.bwp#L14) — `"records-address-changed"`.
- [`integration/legacy-bw6/Processes/account-events/limit-changed.bwp:L14`](../../legacy-bw6/Processes/account-events/limit-changed.bwp#L14) — `"records-limit-changed"`.
- [`integration/legacy-bw6/Processes/account-events/account-closed.bwp:L14`](../../legacy-bw6/Processes/account-events/account-closed.bwp#L14) — `"records-account-closed"`.

**Inference:** precedence and safe concurrent identity reuse are not established by these declarations. The durable-name question directly concerns account-opened, address-changed, limit-changed and account-closed; clientID concerns all EmsConnection users, hence all 24 are listed. Secondary pointer: [spec](specs/account-events/account-opened.md).

**Options**

A. Keep shared clientID and activity durable names subject to broker compatibility.
B. Assign separate client identities and migrate subscriptions explicitly.
C. Use one identity with defined connection/subscription lifecycle.

**Decision:** 

## D-13 Event-fanout queue versus durable topic

**Affected processes:** `account-events.event-fanout`.

**Question:** Should the target consume an anycast queue or a multicast topic with a durable subscription?

**Evidence**

- [`integration/legacy-bw6/Processes/account-events/event-fanout.bwp:L14`](../../legacy-bw6/Processes/account-events/event-fanout.bwp#L14) — `"bw.jms.JMSQueueReceiver"`.
- [`integration/legacy-bw6/Processes/account-events/event-fanout.bwp:L14`](../../legacy-bw6/Processes/account-events/event-fanout.bwp#L14) — `"HB.ACCOUNT.EVENTS.IN"`.
- [`integration/fixture/broker.xml:L28`](../../fixture/broker.xml#L28) — `"<multicast><queue name="records-event-fanout"/></multicast>"`.
- [`integration/corpus/account-events.event-fanout/flow.json:L110`](../../corpus/account-events.event-fanout/flow.json#L110) — `""topic": "HB.ACCOUNT.EVENTS.IN""`.
- [`integration/corpus/account-events.event-fanout/flow.json:L111`](../../corpus/account-events.event-fanout/flow.json#L111) — `""durable_subscription": "records-event-fanout""`.

Secondary pointer: [spec](specs/account-events/event-fanout.md).

**Options**

A. Keep the source queue-receiver declaration.
B. Use the fixture/corpus durable multicast contract.
C. Define an explicit topology bridge or migration.

**Decision:** 

## D-14 Limit-changed per-account ordering

**Affected processes:** `account-events.limit-changed`.

**Question:** Must the target preserve per-account ordering with two consumers, and which key/sequence mapping governs?

**Evidence**

- [`integration/legacy-bw6/Processes/account-events/limit-changed.bwp:L14`](../../legacy-bw6/Processes/account-events/limit-changed.bwp#L14) — `"<sequencingKey>accountId</sequencingKey>"`.
- [`integration/legacy-bw6/Processes/account-events/limit-changed.bwp:L29`](../../legacy-bw6/Processes/account-events/limit-changed.bwp#L29) — `"JMSXGroupID,sequence"`.
- [`integration/corpus/account-events.limit-changed/flow.json:L169`](../../corpus/account-events.limit-changed/flow.json#L169) — `""key_header": "JMSXGroupID""`.
- [`integration/corpus/account-events.limit-changed/flow.json:L170`](../../corpus/account-events.limit-changed/flow.json#L170) — `""sequence_header": "sequence""`.
- [`integration/corpus/account-events.limit-changed/flow.json:L171`](../../corpus/account-events.limit-changed/flow.json#L171) — `""parallel_consumers": 2"`.

The corpus explicitly declares two consumers, not a configured BW consumer count. **Inference:** source accountId sequencing and corpus JMSXGroupID are intended to encode the same per-account contract; their runtime mapping is unverified. Secondary pointer: [spec](specs/account-events/limit-changed.md).

**Options**

A. Keep per-key sequence order under two or more consumers.
B. Serialize processing and document throughput effects.
C. Approve relaxed ordering and explicitly revise parity.

**Decision:** 

## D-15 Payment status import precedence

**Affected processes:** `payments.instruction-intake`, `payments.status-update`.

**Question:** Preserve constant ACCEPTED_RETAIL or change the layered screening/clearing rule?

**Evidence**

- [`integration/legacy-bw6/Processes/payments/instruction-intake.bwp:L21`](../../legacy-bw6/Processes/payments/instruction-intake.bwp#L21) — `"Transforms/payment-status.xsl"`.
- [`integration/legacy-bw6/Processes/payments/status-update.bwp:L19`](../../legacy-bw6/Processes/payments/status-update.bwp#L19) — `"Transforms/payment-status.xsl"`.
- [`integration/legacy-bw6/Transforms/payment-status.xsl:L3`](../../legacy-bw6/Transforms/payment-status.xsl#L3) — `"payments/status-policy.xsl"`.
- [`integration/legacy-bw6/Transforms/payment-status.xsl:L4`](../../legacy-bw6/Transforms/payment-status.xsl#L4) — `"ACCEPTED_RETAIL"`.
- [`integration/legacy-bw6/Transforms/payments/status-policy.xsl:L3`](../../legacy-bw6/Transforms/payments/status-policy.xsl#L3) — `"base/clearing-policy.xsl"`.
- [`integration/legacy-bw6/Transforms/payments/status-policy.xsl:L4`](../../legacy-bw6/Transforms/payments/status-policy.xsl#L4) — `"SCREENED"`.
- [`integration/legacy-bw6/Transforms/payments/base/clearing-policy.xsl:L3`](../../legacy-bw6/Transforms/payments/base/clearing-policy.xsl#L3) — `"../../common/receipt.xsl"`.
- [`integration/legacy-bw6/Transforms/payments/base/clearing-policy.xsl:L4`](../../legacy-bw6/Transforms/payments/base/clearing-policy.xsl#L4) — `"PENDING_CLEARING"`.

**Inference (XSLT import precedence):** the top-level named template wins, yielding ACCEPTED_RETAIL regardless of imported status constants. Secondary pointer: [spec](specs/payments/status-update.md).

**Options**

A. Keep the highest-precedence constant for parity.
B. Define a rule using lower-level policy results.
C. Replace the chain with an approved status contract.

**Decision:** 

## D-16 Currency element versus attribute

**Affected processes:** `payments.currency-routing`.

**Question:** Which representation governs when BPEL, request attribute and nested payment Document disagree?

**Evidence**

- [`integration/legacy-bw6/Processes/payments/currency-routing.bwp:L22`](../../legacy-bw6/Processes/payments/currency-routing.bwp#L22) — `"$Receive/currency = 'USD'"`.
- [`integration/legacy-bw6/Transforms/currency-routing.xsl:L5`](../../legacy-bw6/Transforms/currency-routing.xsl#L5) — `"@currency = 'USD'"`.
- [`integration/legacy-bw6/reference/inputs/payments.currency-routing/currency-routing-02.xml:L2`](../../legacy-bw6/reference/inputs/payments.currency-routing/currency-routing-02.xml#L2) — `"currency="EUR""`.
- [`integration/legacy-bw6/reference/inputs/payments.currency-routing/currency-routing-02.xml:L2`](../../legacy-bw6/reference/inputs/payments.currency-routing/currency-routing-02.xml#L2) — `"InstdAmt Ccy="USD""`.

**Inference:** case 02 conflicts between @currency=EUR and nested InstdAmt/@Ccy=USD, not a direct request/currency element (none exists). It does not demonstrate opposite executed branches of the BPEL test. Secondary pointer: [spec](specs/payments/currency-routing.md).

**Options**

A. Keep both expressions and their distinct behavior.
B. Use the request currency attribute for both decisions.
C. Use validated nested payment currency and reject inconsistencies.

**Decision:** 

## D-17 Retail selector versus payload filtering

**Affected processes:** `customer-alerts.large-transaction`, `customer-alerts.low-balance`.

**Question:** Which rule wins when the JMS customerType property is absent or conflicts with the payload attribute?

**Evidence**

- [`integration/legacy-bw6/Processes/customer-alerts/large-transaction.bwp:L14`](../../legacy-bw6/Processes/customer-alerts/large-transaction.bwp#L14) — `"customerType = &apos;RETAIL&apos;"`.
- [`integration/legacy-bw6/Processes/customer-alerts/low-balance.bwp:L14`](../../legacy-bw6/Processes/customer-alerts/low-balance.bwp#L14) — `"customerType = &apos;RETAIL&apos;"`.
- [`integration/legacy-bw6/Transforms/large-transaction.xsl:L5`](../../legacy-bw6/Transforms/large-transaction.xsl#L5) — `"request[@customerType != 'RETAIL']"`.
- [`integration/legacy-bw6/Transforms/low-balance.xsl:L5`](../../legacy-bw6/Transforms/low-balance.xsl#L5) — `"request[@customerType != 'RETAIL']"`.

**Inference:** XML decoding makes the selector customerType = 'RETAIL'. Missing/conflicting representations can be treated differently by selector evaluation and XSLT matching; business precedence is undeclared. Secondary pointer: [spec](specs/customer-alerts/large-transaction.md).

**Options**

A. Keep separate broker-property and payload filters.
B. Make the JMS property authoritative and validate payload consistency.
C. Make the validated payload authoritative and revise the selector.

**Decision:** 

## D-18 Card-dispute poison audit behavior

**Affected processes:** `customer-alerts.card-dispute`.

**Question:** Where should poison detection, delivery-attempt auditing and dead-letter routing live?

**Evidence**

- [`integration/corpus/customer-alerts.card-dispute/flow.json:L149`](../../corpus/customer-alerts.card-dispute/flow.json#L149) — `""audit_destination": "HB.DELIVERY.AUDIT""`.
- [`integration/corpus/customer-alerts.card-dispute/flow.json:L151`](../../corpus/customer-alerts.card-dispute/flow.json#L151) — `""redeliveries": 3"`.
- [`integration/corpus/customer-alerts.card-dispute/flow.json:L152`](../../corpus/customer-alerts.card-dispute/flow.json#L152) — `""dlq": "HB.UNDLV""`.
- [`integration/legacy-bw6/reference/record.py:L57`](../../legacy-bw6/reference/record.py#L57) — `"request.get("poison") == "true""`.
- [`integration/legacy-bw6/reference/record.py:L60`](../../legacy-bw6/reference/record.py#L60) — `""HB.DELIVERY.AUDIT""`.
- [`integration/legacy-bw6/reference/record.py:L75`](../../legacy-bw6/reference/record.py#L75) — `""HB.DELIVERY.AUDIT""`.
- [`integration/legacy-bw6/reference/record.py:L76`](../../legacy-bw6/reference/record.py#L76) — `""HB.UNDLV""`.
- [`integration/legacy-bw6/Processes/customer-alerts/card-dispute.bwp:L7`](../../legacy-bw6/Processes/customer-alerts/card-dispute.bwp#L7) — `"HB.UNDLV"`.
- [`integration/legacy-bw6/Processes/customer-alerts/card-dispute.bwp:L29`](../../legacy-bw6/Processes/customer-alerts/card-dispute.bwp#L29) — `"HB.DISPUTE.RECEIVED"`.

**Inference (all activities inspected):** no declared activity emits HB.DELIVERY.AUDIT or tests poison. Recorder lines 57–63 construct synthetic expectations; lines 75–76 configure audit/DLQ capture. This does not prove BW audit emission. Secondary pointer: [spec](specs/customer-alerts/card-dispute.md).

**Options**

A. Implement the corpus audit contract in the target consumer.
B. Assign audit/poison behavior to middleware or an external component.
C. Keep declared process behavior and explicitly revise audit expectations.

**Decision:** 

## D-19 Document-store file side effect

**Affected processes:** `statements-documents.document-store`.

**Question:** Is corpus SFTP output or the files.url HTTP interaction authoritative, and who materializes files?

**Evidence**

- [`integration/corpus/statements-documents.document-store/flow.json:L54`](../../corpus/statements-documents.document-store/flow.json#L54) — `""transport": "sftp""`.
- [`integration/corpus/statements-documents.document-store/flow.json:L55`](../../corpus/statements-documents.document-store/flow.json#L55) — `"/upload/out/statements-documents.document-store"`.
- [`integration/legacy-bw6/Processes/statements-documents/document-store.bwp:L24`](../../legacy-bw6/Processes/statements-documents/document-store.bwp#L24) — `"${files.url}"`.
- [`integration/legacy-bw6/Processes/statements-documents/document-store.bwp:L29`](../../legacy-bw6/Processes/statements-documents/document-store.bwp#L29) — `"INSERT INTO document_registry"`.
- [`integration/legacy-bw6/reference/record.py:L69`](../../legacy-bw6/reference/record.py#L69) — `""file-service""`.
- [`integration/legacy-bw6/reference/record.py:L81`](../../legacy-bw6/reference/record.py#L81) — `""/upload/out/""`.

**Inference (complete process inspected):** no SFTPPut is declared. Recorder construction of file-service expectations does not prove an external service writes SFTP files. Secondary pointer: [spec](specs/statements-documents/document-store.md).

**Options**

A. Require external file service output matching the corpus and document its contract.
B. Add an explicit target file-writing step and approved transport.
C. Treat corpus files as model artifacts and revise parity scope.

**Decision:** 

## D-20 Daily-fee static rate cache

**Affected processes:** `fees-billing.daily-fee`.

**Question:** Keep the first rate per accountType across messages, or use per-message rates with concurrency-safe state?

**Evidence**

- [`integration/legacy-bw6/src/com/halvergate/integration/FeeActivities.java:L9`](../../legacy-bw6/src/com/halvergate/integration/FeeActivities.java#L9) — `"new HashMap<>()"`.
- [`integration/legacy-bw6/src/com/halvergate/integration/FeeActivities.java:L14`](../../legacy-bw6/src/com/halvergate/integration/FeeActivities.java#L14) — `"RATES.computeIfAbsent(accountType"`.
- [`integration/legacy-bw6/src/com/halvergate/integration/FeeActivities.java:L15`](../../legacy-bw6/src/com/halvergate/integration/FeeActivities.java#L15) — `"multiply(appliedRate)"`.
- [`integration/legacy-bw6/Processes/fees-billing/daily-fee.bwp:L19`](../../legacy-bw6/Processes/fees-billing/daily-fee.bwp#L19) — `"balance,rate,accountType"`.
- [`integration/fixture/tests/test_estate.py:L53`](../../fixture/tests/test_estate.py#L53) — `"requests[0].get("rate") != requests[1].get("rate")"`.
- [`integration/fixture/tests/test_estate.py:L54`](../../fixture/tests/test_estate.py#L54) — `"["15.00"] * 3"`.

**Inference (Java semantics):** static HashMap retains the first computed rate per key without declared synchronization; concurrent use is not thread-safe. Actual BW instance/thread lifetime is unverified. The fixture freezes three 15.00 values despite differing initial rates. Secondary pointer: [spec](specs/fees-billing/daily-fee.md).

**Options**

A. Keep first-rate-wins with explicit cache lifetime/concurrency rules.
B. Use each message rate with no persistent cache.
C. Use a versioned concurrency-safe external rate store.

**Decision:** 

## D-21 Channel-dependent month-end rounding

**Affected processes:** `fees-billing.month-end-summary`.

**Question:** Keep both rules for parity or unify rounding? Is the differently named fee-rounding stylesheet the intended mapping?

**Evidence**

- [`integration/legacy-bw6/Processes/fees-billing/month-end-summary.bwp:L19`](../../legacy-bw6/Processes/fees-billing/month-end-summary.bwp#L19) — `"roundHalfEven"`.
- [`integration/legacy-bw6/Processes/fees-billing/month-end-summary.bwp:L24`](../../legacy-bw6/Processes/fees-billing/month-end-summary.bwp#L24) — `"Transforms/fee-rounding.xsl"`.
- [`integration/legacy-bw6/Transforms/fee-rounding.xsl:L5`](../../legacy-bw6/Transforms/fee-rounding.xsl#L5) — `"@channel = 'JAVA'"`.
- [`integration/legacy-bw6/Transforms/fee-rounding.xsl:L5`](../../legacy-bw6/Transforms/fee-rounding.xsl#L5) — `"round(xs:decimal(@amount) * 100)"`.
- [`integration/legacy-bw6/src/com/halvergate/integration/FeeActivities.java:L19`](../../legacy-bw6/src/com/halvergate/integration/FeeActivities.java#L19) — `"RoundingMode.HALF_EVEN"`.
- [`integration/corpus/fees-billing.month-end-summary/flow.json:L75`](../../corpus/fees-billing.month-end-summary/flow.json#L75) — `"MONTH_END|2.35|"`.
- [`integration/corpus/fees-billing.month-end-summary/flow.json:L85`](../../corpus/fees-billing.month-end-summary/flow.json#L85) — `"MONTH_END|2.34|"`.
- [`integration/fixture/tests/test_estate.py:L60`](../../fixture/tests/test_estate.py#L60) — `""2.345""`.
- [`integration/fixture/tests/test_estate.py:L61`](../../fixture/tests/test_estate.py#L61) — `"["XSLT", "JAVA"]"`.

**Inference:** name mismatch alone does not prove a mapping defect; the two amounts are explicit corpus expectations. Secondary pointer: [spec](specs/fees-billing/month-end-summary.md).

**Options**

A. Keep both rules and current mapping.
B. Unify on half-even with approved output changes.
C. Unify on the XSLT rule with approved output changes.

**Decision:** 

## D-22 Fee-reversal amount sign

**Affected processes:** `fees-billing.fee-reversal`.

**Question:** Is passing the supplied amount without negation the intended reversal contract?

**Evidence**

- [`integration/legacy-bw6/Transforms/fee-reversal.xsl:L3`](../../legacy-bw6/Transforms/fee-reversal.xsl#L3) — `"common/receipt.xsl"`.
- [`integration/legacy-bw6/Transforms/fee-reversal.xsl:L4`](../../legacy-bw6/Transforms/fee-reversal.xsl#L4) — `"FEE_REVERSAL"`.
- [`integration/legacy-bw6/Transforms/common/receipt.xsl:L6`](../../legacy-bw6/Transforms/common/receipt.xsl#L6) — `"select="@amount""`.
- [`integration/corpus/fees-billing.fee-reversal/flow.json:L60`](../../corpus/fees-billing.fee-reversal/flow.json#L60) — `"FEE_REVERSAL|125.50|"`.

**Inference (stylesheet inspection):** fee-reversal overrides only status; the common amount template passes @amount unchanged. This agrees with the positive corpus amount and the spec section-11 reversal question. Secondary pointer: [spec](specs/fees-billing/fee-reversal.md).

**Options**

A. Keep supplied amount and interpret reversal through status/type.
B. Negate amounts under an approved reversal contract.
C. Validate against original posting and define sign handling per case.

**Decision:** 

## D-23 Shared receipt projection and byte parity

**Affected processes:** `account-events.account-closed`, `account-events.account-opened`, `account-events.address-changed`, `account-events.event-fanout`, `account-events.limit-changed`, `customer-alerts.card-dispute`, `customer-alerts.large-transaction`, `customer-alerts.low-balance`, `customer-alerts.preference-sync`, `fees-billing.daily-fee`, `fees-billing.fee-posting`, `fees-billing.fee-reversal`, `fees-billing.month-end-summary`, `payments.currency-routing`, `payments.instruction-intake`, `payments.payment-returns`, `payments.sanctions-screening`, `payments.status-update`, `payments.validation-enrichment`, `statements-documents.delivery-notice`, `statements-documents.document-store`, `statements-documents.pdf-request`, `statements-documents.split-enrich`, `statements-documents.statement-drop`.

**Question:** Is attribute-only projection, ignoring nested pain.001 content, intended? Which artifacts must be byte-identical?

**Evidence**

- [`integration/legacy-bw6/Transforms/common/receipt.xsl:L3`](../../legacy-bw6/Transforms/common/receipt.xsl#L3) — `"omit-xml-declaration="yes""`.
- [`integration/legacy-bw6/Transforms/common/receipt.xsl:L9`](../../legacy-bw6/Transforms/common/receipt.xsl#L9) — `"match="request""`.
- [`integration/legacy-bw6/Transforms/common/receipt.xsl:L10`](../../legacy-bw6/Transforms/common/receipt.xsl#L10) — `"currency="{@currency}""`.
- [`integration/legacy-bw6/Transforms/common/receipt.xsl:L14`](../../legacy-bw6/Transforms/common/receipt.xsl#L14) — `"concat(@flow,'|',@id,'|',@account,'|')"`.
- [`integration/legacy-bw6/Transforms/statement.xsl:L3`](../../legacy-bw6/Transforms/statement.xsl#L3) — `"statements/layout.xsl"`.
- [`integration/legacy-bw6/Transforms/statements/layout.xsl:L3`](../../legacy-bw6/Transforms/statements/layout.xsl#L3) — `"base/timezone.xsl"`.
- [`integration/legacy-bw6/Transforms/statements/base/timezone.xsl:L3`](../../legacy-bw6/Transforms/statements/base/timezone.xsl#L3) — `"../../common/receipt.xsl"`.
- [`integration/legacy-bw6/reference/inputs/payments.instruction-intake/instruction-intake-01.xml:L2`](../../legacy-bw6/reference/inputs/payments.instruction-intake/instruction-intake-01.xml#L2) — `"urn:iso:std:iso:20022:tech:xsd:pain.001.001.03"`.
- [`integration/harness/README.md:L124`](../../harness/README.md#L124) — `"Message bodies are UTF-8 strings compared byte-for-byte as decoded text."`.

**Inference (import graph/templates inspected):** all 24 processes reach receipt.xsl through 23 distinct top-level referenced stylesheets (payment-status is shared). There are 23 direct receipt importers across the tree: 21 top-level stylesheets and two deeper base sheets, not 23 direct top-level importers. Statement uses layout/timezone; payment-status uses policy/clearing. The common receipt reads request attributes, not nested Document content; overrides add specialized attribute-based logic. Byte parity remains a question, not a decision. Secondary pointer: [spec](specs/payments/instruction-intake.md).

**Options**

A. Preserve projection and frozen byte-level message/file contracts.
B. Use semantic equivalence with approved normalization.
C. Map nested payment content and approve new output contracts.

**Decision:** 

## D-24 Request schema namespace and validation

**Affected processes:** `account-events.account-closed`, `account-events.account-opened`, `account-events.address-changed`, `account-events.event-fanout`, `account-events.limit-changed`, `customer-alerts.card-dispute`, `customer-alerts.large-transaction`, `customer-alerts.low-balance`, `customer-alerts.preference-sync`, `fees-billing.daily-fee`, `fees-billing.fee-posting`, `fees-billing.fee-reversal`, `fees-billing.month-end-summary`, `payments.currency-routing`, `payments.instruction-intake`, `payments.payment-returns`, `payments.sanctions-screening`, `payments.status-update`, `payments.validation-enrichment`, `statements-documents.delivery-notice`, `statements-documents.document-store`, `statements-documents.pdf-request`, `statements-documents.split-enrich`, `statements-documents.statement-drop`.

**Question:** Enforce the qualified schema, accept recorded un-namespaced requests, or normalize at ingress?

**Evidence**

- [`integration/legacy-bw6/Schemas/request.xsd:L2`](../../legacy-bw6/Schemas/request.xsd#L2) — `"targetNamespace="urn:halvergate:integration:request""`.
- [`integration/legacy-bw6/Schemas/request.xsd:L2`](../../legacy-bw6/Schemas/request.xsd#L2) — `"elementFormDefault="qualified""`.
- [`integration/legacy-bw6/reference/inputs/payments.instruction-intake/instruction-intake-01.xml:L2`](../../legacy-bw6/reference/inputs/payments.instruction-intake/instruction-intake-01.xml#L2) — `"<request id="`.
- [`integration/legacy-bw6/Processes/payments/instruction-intake.bwp:L3`](../../legacy-bw6/Processes/payments/instruction-intake.bwp#L3) — `"../../Schemas/request.xsd"`.

**Inference (recorded root and all imports inspected):** the recorded request root has no namespace; nested Document has an ISO namespace. All processes import request.xsd, but that does not prove runtime validation is enabled. Review unqualified XSLT request matching if namespacing changes. Secondary pointer: [spec](specs/account-events/account-opened.md).

**Options**

A. Accept un-namespaced requests without schema enforcement.
B. Normalize to the qualified namespace under an explicit compatibility policy.
C. Enforce the XSD and require producer/fixture changes.

**Decision:** 

## D-25 Missing process or correct export scope

**Affected processes:** `account-events.account-closed`, `account-events.account-opened`, `account-events.address-changed`, `account-events.event-fanout`, `account-events.limit-changed`, `customer-alerts.card-dispute`, `customer-alerts.large-transaction`, `customer-alerts.low-balance`, `customer-alerts.preference-sync`, `fees-billing.daily-fee`, `fees-billing.fee-posting`, `fees-billing.fee-reversal`, `fees-billing.month-end-summary`, `payments.currency-routing`, `payments.instruction-intake`, `payments.payment-returns`, `payments.sanctions-screening`, `payments.status-update`, `payments.validation-enrichment`, `statements-documents.delivery-notice`, `statements-documents.document-store`, `statements-documents.pdf-request`, `statements-documents.split-enrich`, `statements-documents.statement-drop`.

**Question:** The run brief expected 25 .bwp files but the export contains 24. Is a process missing or is 24 the correct scope?

**Evidence**

- [`integration/legacy-bw6/META-INF/MANIFEST.MF:L4`](../../legacy-bw6/META-INF/MANIFEST.MF#L4) — `"Bundle-SymbolicName: halvergate.integration.module"`.
- [`integration/legacy-bw6/META-INF/MANIFEST.MF:L7`](../../legacy-bw6/META-INF/MANIFEST.MF#L7) — `"TIBCO-BW-ModuleType: bw.application.module"`.
- [`integration/legacy-bw6/.project:L2`](../../legacy-bw6/.project#L2) — `"halvergate.integration.module"`.
- [`integration/legacy-bw6/Processes/account-events/account-closed.bwp:L2`](../../legacy-bw6/Processes/account-events/account-closed.bwp#L2) — `"halvergate.account-events.account-closed"`.
- [`integration/legacy-bw6/Processes/account-events/account-opened.bwp:L2`](../../legacy-bw6/Processes/account-events/account-opened.bwp#L2) — `"halvergate.account-events.account-opened"`.
- [`integration/legacy-bw6/Processes/account-events/address-changed.bwp:L2`](../../legacy-bw6/Processes/account-events/address-changed.bwp#L2) — `"halvergate.account-events.address-changed"`.
- [`integration/legacy-bw6/Processes/account-events/event-fanout.bwp:L2`](../../legacy-bw6/Processes/account-events/event-fanout.bwp#L2) — `"halvergate.account-events.event-fanout"`.
- [`integration/legacy-bw6/Processes/account-events/limit-changed.bwp:L2`](../../legacy-bw6/Processes/account-events/limit-changed.bwp#L2) — `"halvergate.account-events.limit-changed"`.
- [`integration/legacy-bw6/Processes/customer-alerts/card-dispute.bwp:L2`](../../legacy-bw6/Processes/customer-alerts/card-dispute.bwp#L2) — `"halvergate.customer-alerts.card-dispute"`.
- [`integration/legacy-bw6/Processes/customer-alerts/large-transaction.bwp:L2`](../../legacy-bw6/Processes/customer-alerts/large-transaction.bwp#L2) — `"halvergate.customer-alerts.large-transaction"`.
- [`integration/legacy-bw6/Processes/customer-alerts/low-balance.bwp:L2`](../../legacy-bw6/Processes/customer-alerts/low-balance.bwp#L2) — `"halvergate.customer-alerts.low-balance"`.
- [`integration/legacy-bw6/Processes/customer-alerts/preference-sync.bwp:L2`](../../legacy-bw6/Processes/customer-alerts/preference-sync.bwp#L2) — `"halvergate.customer-alerts.preference-sync"`.
- [`integration/legacy-bw6/Processes/fees-billing/daily-fee.bwp:L2`](../../legacy-bw6/Processes/fees-billing/daily-fee.bwp#L2) — `"halvergate.fees-billing.daily-fee"`.
- [`integration/legacy-bw6/Processes/fees-billing/fee-posting.bwp:L2`](../../legacy-bw6/Processes/fees-billing/fee-posting.bwp#L2) — `"halvergate.fees-billing.fee-posting"`.
- [`integration/legacy-bw6/Processes/fees-billing/fee-reversal.bwp:L2`](../../legacy-bw6/Processes/fees-billing/fee-reversal.bwp#L2) — `"halvergate.fees-billing.fee-reversal"`.
- [`integration/legacy-bw6/Processes/fees-billing/month-end-summary.bwp:L2`](../../legacy-bw6/Processes/fees-billing/month-end-summary.bwp#L2) — `"halvergate.fees-billing.month-end-summary"`.
- [`integration/legacy-bw6/Processes/payments/currency-routing.bwp:L2`](../../legacy-bw6/Processes/payments/currency-routing.bwp#L2) — `"halvergate.payments.currency-routing"`.
- [`integration/legacy-bw6/Processes/payments/instruction-intake.bwp:L2`](../../legacy-bw6/Processes/payments/instruction-intake.bwp#L2) — `"halvergate.payments.instruction-intake"`.
- [`integration/legacy-bw6/Processes/payments/payment-returns.bwp:L2`](../../legacy-bw6/Processes/payments/payment-returns.bwp#L2) — `"halvergate.payments.payment-returns"`.
- [`integration/legacy-bw6/Processes/payments/sanctions-screening.bwp:L2`](../../legacy-bw6/Processes/payments/sanctions-screening.bwp#L2) — `"halvergate.payments.sanctions-screening"`.
- [`integration/legacy-bw6/Processes/payments/status-update.bwp:L2`](../../legacy-bw6/Processes/payments/status-update.bwp#L2) — `"halvergate.payments.status-update"`.
- [`integration/legacy-bw6/Processes/payments/validation-enrichment.bwp:L2`](../../legacy-bw6/Processes/payments/validation-enrichment.bwp#L2) — `"halvergate.payments.validation-enrichment"`.
- [`integration/legacy-bw6/Processes/statements-documents/delivery-notice.bwp:L2`](../../legacy-bw6/Processes/statements-documents/delivery-notice.bwp#L2) — `"halvergate.statements-documents.delivery-notice"`.
- [`integration/legacy-bw6/Processes/statements-documents/document-store.bwp:L2`](../../legacy-bw6/Processes/statements-documents/document-store.bwp#L2) — `"halvergate.statements-documents.document-store"`.
- [`integration/legacy-bw6/Processes/statements-documents/pdf-request.bwp:L2`](../../legacy-bw6/Processes/statements-documents/pdf-request.bwp#L2) — `"halvergate.statements-documents.pdf-request"`.
- [`integration/legacy-bw6/Processes/statements-documents/split-enrich.bwp:L2`](../../legacy-bw6/Processes/statements-documents/split-enrich.bwp#L2) — `"halvergate.statements-documents.split-enrich"`.
- [`integration/legacy-bw6/Processes/statements-documents/statement-drop.bwp:L2`](../../legacy-bw6/Processes/statements-documents/statement-drop.bwp#L2) — `"halvergate.statements-documents.statement-drop"`.

**Inference (recursive filesystem inventory):** exactly 24 .bwp files exist, all under Processes/*/; META-INF contains only MANIFEST.MF and .project contains module metadata, not another process. Neither metadata file declares a process count or proves completeness. The expectation of 25 comes from the run brief, not source. [Graph inventory](graph.json) records the observed declarations.

**Options**

A. Confirm 24 as complete scope and correct the external brief.
B. Obtain the missing process/export before planning conversion.
C. Approve partial 24-process scope while tracking the missing artifact.

**Decision:** 

## Decision index

| ID | Title | Affected processes | Kind |
| --- | --- | --- | --- |
| D-01 | Screening API version by environment | `payments.sanctions-screening`, `statements-documents.pdf-request`, `payments.instruction-intake`, `statements-documents.statement-drop` | environment-difference |
| D-02 | PDF request endpoint ownership | `statements-documents.pdf-request`, `payments.sanctions-screening` | semantics |
| D-03 | Environment credentials and literal hosts | `account-events.account-closed`, `account-events.account-opened`, `account-events.address-changed`, `account-events.event-fanout`, `account-events.limit-changed`, `customer-alerts.card-dispute`, `customer-alerts.large-transaction`, `customer-alerts.low-balance`, `customer-alerts.preference-sync`, `fees-billing.daily-fee`, `fees-billing.fee-posting`, `fees-billing.fee-reversal`, `fees-billing.month-end-summary`, `payments.currency-routing`, `payments.instruction-intake`, `payments.payment-returns`, `payments.sanctions-screening`, `payments.status-update`, `payments.validation-enrichment`, `statements-documents.delivery-notice`, `statements-documents.document-store`, `statements-documents.pdf-request`, `statements-documents.split-enrich`, `statements-documents.statement-drop` | environment-difference |
| D-04 | Call-process binding and independent starters | `account-events.event-fanout`, `account-events.account-opened`, `account-events.address-changed`, `account-events.limit-changed`, `account-events.account-closed`, `payments.instruction-intake`, `payments.validation-enrichment`, `payments.sanctions-screening`, `payments.currency-routing`, `payments.status-update`, `statements-documents.statement-drop`, `statements-documents.split-enrich`, `statements-documents.pdf-request`, `statements-documents.document-store`, `statements-documents.delivery-notice` | semantics |
| D-05 | External entry producers and output consumers | `account-events.event-fanout`, `customer-alerts.card-dispute`, `customer-alerts.large-transaction`, `customer-alerts.low-balance`, `customer-alerts.preference-sync`, `fees-billing.daily-fee`, `fees-billing.fee-posting`, `fees-billing.fee-reversal`, `payments.instruction-intake`, `payments.payment-returns`, `statements-documents.statement-drop` | uncalled-or-orphan |
| D-06 | Month-end-summary entry and scope | `fees-billing.month-end-summary` | uncalled-or-orphan |
| D-07 | Daily-fee timer or queue listener | `fees-billing.daily-fee` | semantics |
| D-08 | Statement-drop transport and file rejection | `statements-documents.statement-drop` | semantics |
| D-09 | Transaction and acknowledgement boundary | `account-events.account-closed`, `account-events.account-opened`, `account-events.address-changed`, `account-events.event-fanout`, `account-events.limit-changed`, `customer-alerts.card-dispute`, `customer-alerts.large-transaction`, `customer-alerts.low-balance`, `customer-alerts.preference-sync`, `fees-billing.daily-fee`, `fees-billing.fee-posting`, `fees-billing.fee-reversal`, `fees-billing.month-end-summary`, `payments.currency-routing`, `payments.instruction-intake`, `payments.payment-returns`, `payments.sanctions-screening`, `payments.status-update`, `payments.validation-enrichment`, `statements-documents.delivery-notice`, `statements-documents.document-store`, `statements-documents.pdf-request`, `statements-documents.split-enrich`, `statements-documents.statement-drop` | transaction |
| D-10 | HTTP side effects, response use and parity coverage | `payments.sanctions-screening`, `statements-documents.pdf-request`, `statements-documents.document-store`, `fees-billing.fee-posting`, `customer-alerts.preference-sync` | semantics |
| D-11 | Dead-letter ownership and drain contract | `account-events.account-closed`, `account-events.account-opened`, `account-events.address-changed`, `account-events.event-fanout`, `account-events.limit-changed`, `customer-alerts.card-dispute`, `customer-alerts.large-transaction`, `customer-alerts.low-balance`, `customer-alerts.preference-sync`, `fees-billing.daily-fee`, `fees-billing.fee-posting`, `fees-billing.fee-reversal`, `fees-billing.month-end-summary`, `payments.currency-routing`, `payments.instruction-intake`, `payments.payment-returns`, `payments.sanctions-screening`, `payments.status-update`, `payments.validation-enrichment`, `statements-documents.delivery-notice`, `statements-documents.document-store`, `statements-documents.pdf-request`, `statements-documents.split-enrich`, `statements-documents.statement-drop` | semantics |
| D-12 | Durable subscriber and shared client identity | `account-events.account-closed`, `account-events.account-opened`, `account-events.address-changed`, `account-events.event-fanout`, `account-events.limit-changed`, `customer-alerts.card-dispute`, `customer-alerts.large-transaction`, `customer-alerts.low-balance`, `customer-alerts.preference-sync`, `fees-billing.daily-fee`, `fees-billing.fee-posting`, `fees-billing.fee-reversal`, `fees-billing.month-end-summary`, `payments.currency-routing`, `payments.instruction-intake`, `payments.payment-returns`, `payments.sanctions-screening`, `payments.status-update`, `payments.validation-enrichment`, `statements-documents.delivery-notice`, `statements-documents.document-store`, `statements-documents.pdf-request`, `statements-documents.split-enrich`, `statements-documents.statement-drop` | semantics |
| D-13 | Event-fanout queue versus durable topic | `account-events.event-fanout` | semantics |
| D-14 | Limit-changed per-account ordering | `account-events.limit-changed` | semantics |
| D-15 | Payment status import precedence | `payments.instruction-intake`, `payments.status-update` | transform |
| D-16 | Currency element versus attribute | `payments.currency-routing` | semantics |
| D-17 | Retail selector versus payload filtering | `customer-alerts.large-transaction`, `customer-alerts.low-balance` | semantics |
| D-18 | Card-dispute poison audit behavior | `customer-alerts.card-dispute` | semantics |
| D-19 | Document-store file side effect | `statements-documents.document-store` | semantics |
| D-20 | Daily-fee static rate cache | `fees-billing.daily-fee` | java-state |
| D-21 | Channel-dependent month-end rounding | `fees-billing.month-end-summary` | transform |
| D-22 | Fee-reversal amount sign | `fees-billing.fee-reversal` | semantics |
| D-23 | Shared receipt projection and byte parity | `account-events.account-closed`, `account-events.account-opened`, `account-events.address-changed`, `account-events.event-fanout`, `account-events.limit-changed`, `customer-alerts.card-dispute`, `customer-alerts.large-transaction`, `customer-alerts.low-balance`, `customer-alerts.preference-sync`, `fees-billing.daily-fee`, `fees-billing.fee-posting`, `fees-billing.fee-reversal`, `fees-billing.month-end-summary`, `payments.currency-routing`, `payments.instruction-intake`, `payments.payment-returns`, `payments.sanctions-screening`, `payments.status-update`, `payments.validation-enrichment`, `statements-documents.delivery-notice`, `statements-documents.document-store`, `statements-documents.pdf-request`, `statements-documents.split-enrich`, `statements-documents.statement-drop` | transform |
| D-24 | Request schema namespace and validation | `account-events.account-closed`, `account-events.account-opened`, `account-events.address-changed`, `account-events.event-fanout`, `account-events.limit-changed`, `customer-alerts.card-dispute`, `customer-alerts.large-transaction`, `customer-alerts.low-balance`, `customer-alerts.preference-sync`, `fees-billing.daily-fee`, `fees-billing.fee-posting`, `fees-billing.fee-reversal`, `fees-billing.month-end-summary`, `payments.currency-routing`, `payments.instruction-intake`, `payments.payment-returns`, `payments.sanctions-screening`, `payments.status-update`, `payments.validation-enrichment`, `statements-documents.delivery-notice`, `statements-documents.document-store`, `statements-documents.pdf-request`, `statements-documents.split-enrich`, `statements-documents.statement-drop` | semantics |
| D-25 | Missing process or correct export scope | `account-events.account-closed`, `account-events.account-opened`, `account-events.address-changed`, `account-events.event-fanout`, `account-events.limit-changed`, `customer-alerts.card-dispute`, `customer-alerts.large-transaction`, `customer-alerts.low-balance`, `customer-alerts.preference-sync`, `fees-billing.daily-fee`, `fees-billing.fee-posting`, `fees-billing.fee-reversal`, `fees-billing.month-end-summary`, `payments.currency-routing`, `payments.instruction-intake`, `payments.payment-returns`, `payments.sanctions-screening`, `payments.status-update`, `payments.validation-enrichment`, `statements-documents.delivery-notice`, `statements-documents.document-store`, `statements-documents.pdf-request`, `statements-documents.split-enrich`, `statements-documents.statement-drop` | scope |
