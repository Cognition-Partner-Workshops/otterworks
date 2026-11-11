# BW6 conversion decisions

Run **tib-d1111**. The export contains **24 processes**. Only environment differences, uncalled/unfed entries and flow-specific apparent defects or ambiguities require decisions here. Nothing is decided. Cross-cutting platform preconditions are in [Wave 0](wave-plan.md#wave-0--groundwork-no-processes). Absence findings are bounded to this export, not the deployed estate; runtime behaviour is not certified.

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

**Inference:** instruction-intake and statement-drop are indirectly affected if their call references resolve (Wave 0). Secondary pointer: [spec](specs/payments/sanctions-screening.md).

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

## D-03 Uncalled or unfed entry flows

**Affected processes:** `account-events.event-fanout`, `customer-alerts.card-dispute`, `customer-alerts.large-transaction`, `customer-alerts.low-balance`, `customer-alerts.preference-sync`, `fees-billing.daily-fee`, `fees-billing.fee-posting`, `fees-billing.fee-reversal`, `payments.instruction-intake`, `payments.payment-returns`, `statements-documents.statement-drop`.

**Question:** Confirm an external producer/invoker for each flow below or approve retirement. Month-end-summary has a separate internal-start question (D-04).

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

**Inference (source-derived [graph summary](graph.json)):** 12 processes have neither an incoming call nor an in-project starter producer. Excluding month-end-summary leaves 11 entry candidates: `account-events.event-fanout`, `customer-alerts.card-dispute`, `customer-alerts.large-transaction`, `customer-alerts.low-balance`, `customer-alerts.preference-sync`, `fees-billing.daily-fee`, `fees-billing.fee-posting`, `fees-billing.fee-reversal`, `payments.instruction-intake`, `payments.payment-returns`, `statements-documents.statement-drop`. Absence from this export does not prove absence in the deployed estate. Secondary pointer: [spec](specs/customer-alerts/card-dispute.md).

**Options**

A. Document external producers/consumers and keep confirmed flows.
B. Retire individually confirmed unused flows or destinations.
C. Add explicitly owned paths for confirmed missing dependencies.

**Decision:**

## D-04 Month-end-summary entry and scope

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

## D-05 Daily-fee timer or queue listener

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

## D-06 Statement-drop transport and file rejection

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

## D-07 Event-fanout queue versus durable topic

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

## D-08 Payment status import precedence

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

## D-09 Document-store file side effect

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

## D-10 Daily-fee static rate cache

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

## D-11 Fee-reversal amount sign

**Affected processes:** `fees-billing.fee-reversal`.

**Question:** Is passing the supplied amount without negation the intended reversal contract?

**Evidence**

- [`integration/legacy-bw6/Processes/fees-billing/fee-reversal.bwp:L19`](../../legacy-bw6/Processes/fees-billing/fee-reversal.bwp#L19) — `"Transforms/fee-reversal.xsl"`.
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

## D-12 Instruction-intake XA scope ends before calls

**Affected processes:** `payments.instruction-intake`.

**Question:** Preserve the committed posting before downstream calls, or approve a different recovery boundary?

**Evidence**

- [`integration/legacy-bw6/Processes/payments/instruction-intake.bwp:L12`](../../legacy-bw6/Processes/payments/instruction-intake.bwp#L12) — `"transactionType="XA""`.
- [`integration/legacy-bw6/Processes/payments/instruction-intake.bwp:L26`](../../legacy-bw6/Processes/payments/instruction-intake.bwp#L26) — `"TRANSACTION_GROUP"`.
- [`integration/legacy-bw6/Processes/payments/instruction-intake.bwp:L31`](../../legacy-bw6/Processes/payments/instruction-intake.bwp#L31) — `"TRANSACTION_GROUP"`.
- [`integration/legacy-bw6/Processes/payments/instruction-intake.bwp:L16`](../../legacy-bw6/Processes/payments/instruction-intake.bwp#L16) — `"HB.PAYMENT.INSTRUCTIONS"`.
- [`integration/legacy-bw6/Processes/payments/instruction-intake.bwp:L36`](../../legacy-bw6/Processes/payments/instruction-intake.bwp#L36) — `"HB.PAYMENT.STATUS"`.
- [`integration/legacy-bw6/Processes/payments/instruction-intake.bwp:L40`](../../legacy-bw6/Processes/payments/instruction-intake.bwp#L40) — `"</bpws:scope>"`.
- [`integration/legacy-bw6/Processes/payments/instruction-intake.bwp:L43`](../../legacy-bw6/Processes/payments/instruction-intake.bwp#L43) — `"payments.validation-enrichment"`.
- [`integration/legacy-bw6/Processes/payments/instruction-intake.bwp:L48`](../../legacy-bw6/Processes/payments/instruction-intake.bwp#L48) — `"payments.sanctions-screening"`.
- [`integration/legacy-bw6/Processes/payments/instruction-intake.bwp:L53`](../../legacy-bw6/Processes/payments/instruction-intake.bwp#L53) — `"payments.currency-routing"`.
- [`integration/legacy-bw6/Processes/payments/instruction-intake.bwp:L58`](../../legacy-bw6/Processes/payments/instruction-intake.bwp#L58) — `"payments.status-update"`.
- [`integration/legacy-bw6/Database/schema.sql:L8`](../../legacy-bw6/Database/schema.sql#L8) — `"PRIMARY KEY (flow, request_id)"`.

**Inference:** Receive, both TRANSACTION_GROUP inserts and Publish are inside PostingTransaction; four callprocess activities follow its closing tag. If names resolve and a call fails after scope commit, earlier work cannot be rolled back by that scope. Whether JMSConfirm can redeliver an already committed consume is unverified; a retry would collide on the primary key. Decide recovery without assuming observed BW execution.

**Options**

A. Preserve the split with an explicit recovery contract.
B. Approve a wider boundary or compensating workflow.

**Decision:**
