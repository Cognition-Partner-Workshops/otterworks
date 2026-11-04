# Claims hub inventory and wave plan (BizTalk Server 2016 to Java 21, Spring Boot 3.3, Apache Camel 4)

Inventory of `ThistlecombeMutual.ClaimsHub` as exported in this directory at fixture commit `24096535f`, read from the artefacts themselves (`Bindings/ClaimsHub.BindingInfo.xml`, `Orchestrations/*.odx`, `Maps/*.btm` and `*.xslt`, `Schemas/*.xsd`, `Pipelines/*.btp` and `Components/*.cs`, `Rules/*.xml`) and checked against `ESTATE.md`. Where the artefact and `ESTATE.md` disagree, the artefact is quoted and the disagreement is listed under [Divergences](#divergences-that-need-a-decision). Target stack and rules follow the carrier modernization standard: pin first, XSLT stays XSLT only where the map is pure, money is `BigDecimal` at scale 2 with a named rounding mode, one row per unit in every report, and divergences are decided by a person.

Counts: 3 receive ports (3 locations), 11 send ports (8 used by orchestrations, 3 filter-only), 3 orchestrations, 8 maps (2 pure, 6 with functoids, 2 of those with inline C#), 11 schemas (1 envelope, 1 flat file, 2 multi-root, 1 property schema), 2 custom pipelines with 2 custom components, 1 BRE policy with 7 rules.

Risk marks: **H** the Camel construct does not give the BizTalk guarantee for free (persistence, transactions, compensation, publish/subscribe) and needs design plus a characterization test; **M** direct counterpart exists but a setting or a number has to be carried over exactly; **L** one-to-one.

## Baseline (pinned before anything moves)

`make check` on `devin/1792473658-insurance-biztalk-fixture` at `24096535f` (Python 3.12, `saxonche==12.5.0`):

```
Fnol_to_CanonicalClaim: 16/16 match
CanonicalClaim_to_PolicyInqRq: 16/16 match
Claim_PolicyInqRs_to_InsertClaim: 16/16 match
InsertClaim_to_TriageFacts: 16/16 match
Payment_to_VendorRemittance: 14/14 match
Payment_to_LedgerPost: 14/14 match
AssignmentRequest_to_RosterQuery: 10/10 match
Roster_AssignmentRequest_to_Notice: 10/10 match
total messages 112, failures 0
vendor-remittance-ff: 14 files, failures 0
triage: 16 claims, failures 0
```

The gate is green, and since `24096535f` the 14 vendor files also pass the hub's own trailer guard (`TrailerTotalsComponent.Check`), which `make check` does not run; see [D1](#d1-resolved-vendor-remittance-goldens-carried-exponent-form-amounts).

## 1. Ports (`Bindings/ClaimsHub.BindingInfo.xml`)

### Receive ports

| Port / location | Transport | Direction | Pipeline | Map on the port | Settings that carry behaviour | Camel counterpart | Risk |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `rp_Agency_FnolBatch_SFTP` / `rl_Agency_FnolBatch_SFTP` | SFTP `sftp.thistlecombe.example:22/agencies/*/fnol/*.xml`, public key | one-way receive | `FnolBatchReceivePipeline` (custom) | none | Service window 22:00 to 06:00; polls every 5 min; max 50 files per poll; `RouteFailedMessage=true`; no host key setting in the binding (the two SFTP send ports pin theirs) | `sftp:` consumer with a Quartz cron scheduler (`0 0/5 22-23,0-5 * * ?`), `maxMessagesPerPoll=50`, recursive agency folders; failed messages to a dead letter channel | M |
| `rp_ClaimsSystem_PaymentInstruction_FILE` / `rl_ClaimsSystem_PaymentInstruction_FILE` | FILE `\\CLAIMS-FS01\disbursements\out\PI-*.xml` | one-way receive | `XMLReceive` | none | Poll 60 s, batch 20, rename received files; `RouteFailedMessage=true` | `file:` (or SMB) consumer, `include=PI-.*\.xml`, `maxMessagesPerPoll=20`, read-lock rename | L |
| `rp_ClaimsSystem_AssignmentRequest_WcfSql` / `rl_ClaimsSystem_AssignmentRequest_WcfSql` | WCF-SQL `mssql://CLAIMS-SQL01//ClaimsCore?InboundId=AssignmentRequests`, TypedPolling | one-way receive | `XMLReceive` | none (the inbound map was removed in `47ac76d`; `AdjusterAssignment` maps in its own branch 1) | Data-available `SELECT COUNT(*) FROM dbo.AssignmentQueue WHERE Status = 'NEW'`; polling `EXEC dbo.usp_PollAssignmentRequests` every 30 s in an ambient transaction | `sql:` consumer (or `sql-stored:` with a timer) in a Spring transaction, 30 s delay; the poll-and-mark must stay in one transaction | M |

### Send ports

| Port | Transport | Direction | Pipeline (send / receive) | Map on the port | Filter | Settings that carry behaviour | Camel counterpart | Risk |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `sp_PolicyAdmin_PolicyInq_WcfSql` | WCF-SQL `POLADM-SQL01//PolicyAdmin`, `TypedProcedure/dbo/usp_GetPolicyAsOf` | solicit-response | `XMLTransmit` / `XMLReceive` | none (the outbound map was removed in `47ac76d`; `Construct_PolicyRq` in `FnolIntake` maps) | none (orchestration-bound) | Retry 3 x 5 min, timeout 1 min | `xslt-saxon:` then `sql-stored:usp_GetPolicyAsOf`, inside the FNOL route's `enrich()` | L |
| `sp_ClaimsDb_InsertClaim_WcfSql` | WCF-SQL `CLAIMS-SQL01//ClaimsCore`, `usp_InsertClaim` | one-way send | `XMLTransmit` | none | none (orchestration-bound) | **Ordered delivery**, ambient transaction, retry 3 x 5 min | `sql-stored:usp_InsertClaim` from a single-consumer endpoint (ordered), transacted | M |
| `sp_ClaimsDb_LedgerPost_WcfSql` | WCF-SQL `CLAIMS-SQL01//ClaimsLedger`, `usp_PostClaimPayment` | one-way send | `XMLTransmit` | none | none (orchestration-bound) | **Retry 0** (orchestration owns retry and compensation), ordered delivery, ambient transaction | `sql-stored:usp_PostClaimPayment` with `maximumRedeliveries=0`, inside the saga step | H (part of the saga) |
| `sp_ClaimsDb_RosterQuery_WcfSql` | WCF-SQL `CLAIMS-SQL01//ClaimsCore`, `usp_GetAdjusterRoster` | solicit-response | `XMLTransmit` / `XMLReceive` | none | none (orchestration-bound) | Retry 3 x 5 min | `sql-stored:usp_GetAdjusterRoster` in a multicast branch | L |
| `sp_PaymentVendor_Remittance_SFTP` | SFTP `sftp.payvendor.example:22/inbound/thistlecombe/REM_%datetime_bts2000%_%SourceFileName%.txt`, public key | solicit-response (vendor ack) | `VendorRemittanceSendPipeline` (custom) / `PassThruReceive` | none | none (orchestration-bound) | **Service window 22:00 to 05:30**, ordered delivery, retry 3 x 10 min, host key pinned (`AccessAnySSHServerHostKey=0`, ed25519 fingerprint) | Bindy/BeanIO fixed-length marshal, trailer guard processor, `sftp:` producer behind a route policy that only opens in the window; file name built from a header | H (window plus port retry plus orchestration retry; see [D6](#d6-two-retry-layers-and-a-service-window-on-the-vendor-send)) |
| `sp_Adjuster_AssignmentNotice_SMTP` | SMTP `mailto:%ClaimsHub.NoticeTo%`, relay `smtp-relay.thistlecombe.example` | one-way send | `XMLTransmit` | none | none (orchestration-bound) | To, Subject, Body from context properties `NoticeTo`, `NoticeSubject`, `NoticeBody`, message part as attachment | `smtp:` with `To`, `Subject` headers and body set from the `AssignmentNotice` fields | M (the three properties are not in `PropertySchema.xsd`; see long tail) |
| `sp_Ops_PaymentHeld_SMTP` | SMTP `mailto:claims-payments-ops@thistlecombe.example` | one-way send | `PassThruTransmit` | none | none (orchestration-bound) | Subject `Payment held: %ClaimsHub.ClaimNumber%` | `smtp:` in the saga's failure path | L |
| `sp_Compliance_AssignmentArchive_FILE` | FILE `\\CLAIMS-FS01\compliance\assignments\%Year%\%MessageID%.xml` | one-way send | `XMLTransmit` | none | none (orchestration-bound) | Temp file on write, seven-year retention | `file:` with `fileName=${date:now:yyyy}/${exchangeId}.xml`, `tempPrefix` | L |
| `sp_Fraud_Referral_FILE` | FILE `\\CLAIMS-FS01\fraud-desk\referrals\%ClaimsHub.ClaimNumber%.xml` | one-way send | `XMLTransmit` | none | `BTS.MessageType == ...claims/triage#TriageFacts` AND `TriageOutcome == FRAUD_REVIEW` | Retry 3 x 5 min | content-based router branch to `file:` | H (filter-only; see below and [D3](#d3-the-filter-only-subscriptions-have-nothing-to-match-in-the-export)) |
| `sp_Declines_FILE` | FILE `\\CLAIMS-FS01\agency-liaison\declines\%ClaimsHub.AgencyId%\%ClaimsHub.ClaimNumber%.xml` | one-way send | `XMLTransmit` | none | `BTS.MessageType == ...claims/triage#TriageFacts` AND `TriageOutcome == DECLINE_NOT_IN_FORCE` | Retry 3 x 5 min | content-based router branch to `file:` with an agency sub-folder | H (as above) |
| `sp_GlassVendor_FastTrack_SFTP` | SFTP `sftp.glassnet.example:22/thistlecombe/fasttrack/%ClaimsHub.ClaimNumber%.xml`, public key | one-way send | `XMLTransmit` | none | `BTS.MessageType == ...TypedProcedures/dbo#usp_InsertClaim` AND `TriageOutcome == FAST_TRACK` AND `LossCauseCd == GLAS` | Retry 3 x 10 min, host key pinned (`AccessAnySSHServerHostKey=0`, ed25519 fingerprint, added in `47ac76d`) | content-based router branch (wire tap off the insert) to `sftp:` with `knownHostsFile` holding the same key | H (as above) |

### The three filter-only subscriptions

No orchestration sends to these ports; BizTalk delivers a copy of any published message whose promoted properties match. In Camel there is no MessageBox, so each becomes an explicit branch of a content-based router placed where the message is produced. Expected destinations over the corpus, from `corpus/golden/triage/` and `corpus/golden/insert-claim/`:

| Port | Filter (all statements AND-ed, one group) | Camel shape | Claims in the corpus that must land there |
| --- | --- | --- | --- |
| `sp_Fraud_Referral_FILE` | message type `TriageFacts`, `TriageOutcome = FRAUD_REVIEW` | `choice().when(header("TriageOutcome").isEqualTo("FRAUD_REVIEW"))` after triage, `to(file:...)` with the `TriageFacts` body | 3: `CLM-2026-100405`, `CLM-2026-100410`, `CLM-2026-100413` |
| `sp_Declines_FILE` | message type `TriageFacts`, `TriageOutcome = DECLINE_NOT_IN_FORCE` | same router, `when(... "DECLINE_NOT_IN_FORCE")`, file name `${header.AgencyId}/${header.ClaimNumber}.xml`, then `stop()` | 4: `CLM-2026-100403` and `CLM-2026-100415` (AG-0417), `CLM-2026-100407` (AG-0922), `CLM-2026-100411` (AG-1305) |
| `sp_GlassVendor_FastTrack_SFTP` | message type `usp_InsertClaim`, `TriageOutcome = FAST_TRACK`, `LossCauseCd = GLAS` | `wireTap` or `multicast` after the insert, `filter(and(TriageOutcome == FAST_TRACK, LossCauseCd == GLAS))`, `to(sftp:...)` with the `usp_InsertClaim` body | 2: `CLM-2026-100400`, `CLM-2026-100401` (`CLM-2026-100411` is GLAS but declined) |

## 2. Orchestrations (`Orchestrations/`)

Every shape below carries behaviour; plain sends and receives that only bind to a port are covered in section 1.

### `FnolIntake.odx`

| Shape (XLANG/s) | What it does | Camel counterpart | Risk |
| --- | --- | --- | --- |
| `Receive_Fnol`, activating, `initialize ClaimNumberCorrelation` (correlation type on `ClaimsHub.PropertySchema.ClaimNumber`) | One instance per claim number | **Aggregator** keyed on header `ClaimNumber` (promoted by the split) | H |
| `Listen_Correction`: `Receive_Correction` following `ClaimNumberCorrelation`, against `Delay_CorrectionWindow` 15 min | A correction inside 15 min replaces the first FNOL; after the window a new instance starts | Same aggregator: `completionTimeout(15 min)`, `UseLatestAggregationStrategy`, persistent `JdbcAggregationRepository` on PostgreSQL so the window survives a restart (BizTalk dehydrates the instance) | H (see [D2](#d2-fnolintake-as-exported-does-not-do-what-estatemd-says)) |
| `Construct_Canonical` / `Construct_Canonical_From_Correction`, map `Fnol_to_CanonicalClaim` | Canonical claim | Java transformer bean (wave 1) | L once wave 1 is done |
| `Construct_PolicyRq` + `Send_PolicyRq` / `Receive_PolicyRs` | Policy lookup as of loss date | **Content enricher**: `enrich("direct:policyLookup", aggregationStrategy)` | L |
| `Construct_InsertClaim`, two-source map `Claim_PolicyInqRs_to_InsertClaim` | BizTalk builds an `aggschema` `Root` with `InputMessagePart_0/1` | The enricher's aggregation strategy hands both documents to the Java transformer (no aggregate envelope needed) | M |
| `Construct_TriageFacts`, map `InsertClaim_to_TriageFacts` | Facts for the policy | Java transformer bean | L once wave 1 is done |
| `Call_Rules ClaimTriage`: **atomic scope** `TriageTx` running `new Microsoft.RuleEngine.Policy("ClaimTriage").Execute(msgTriageFacts)`, then `Expression_ReadOutcome` | The Rule Engine resolves the highest deployed policy version and writes `Outcome` and `Reason` into the facts; the outcome is read back by XPath. The atomic scope is there because the designer requires it, not to protect a resource | `.bean(ClaimTriagePolicy.class)` then `setHeader("TriageOutcome", ...)`; no transaction; the policy version becomes a deploy-time property of the Java build | H (agenda semantics; see [D4](#d4-bre-agenda-semantics-versus-the-reference-evaluator)) |
| `Decide_Outcome` | Declines stop here; everything else is inserted | **Content-based router** `choice()` | L |
| `Terminate` on `DECLINE_NOT_IN_FORCE` | Ends the instance; nothing inserted | `to(declines)` then `stop()` | M (the declines file must still be written; see D3) |
| `Construct_InsertClaim_WithOutcome` (message assignment, sets the `TriageOutcome` field and context property) | Outcome stamped on the insert | `setHeader` plus an XPath/JAXB set on the body | L |
| `Decide_Assignment` (`triageOutcome != "FAST_TRACK"`) + send `msgAssignment` from `AssignmentFactory.FromInsertClaim` | Non-fast-track claims get an adjuster | `filter()` then `to("direct:adjusterAssignment")` (or a durable queue); `AssignmentFactory` reimplemented in Java | M (`AssignmentFactory` exists by name only) |

### `ClaimPayment.odx`

| Shape (XLANG/s) | What it does | Camel counterpart | Risk |
| --- | --- | --- | --- |
| `Receive_Instruction`, activating | One instance per payment instruction | `from(file:...)` | L |
| `Scope_Payment`: **long-running scope** `PaymentTx` | Holds the ledger post open across a vendor window that can take hours | **Saga** EIP (`saga().propagation(REQUIRES_NEW)`), with a persistent saga service (LRA coordinator or a JDBC-backed `CamelSagaService`) so a restart mid-window still compensates | H |
| `Scope_LedgerPost`: **atomic scope** `LedgerTx` with a **compensation** block sending `ReversePayment` with the same document | One post, compensated by one reversal | Saga step `.compensation("direct:reverseLedgerPost")` around a `transacted()` call to `usp_PostClaimPayment`; the reversal sends the identical `usp_PostClaimPayment` document to the reversal action | H |
| `Construct_LedgerPost`, map `Payment_to_LedgerPost` | Ledger amounts and vendor reference | Java transformer bean | M (money) |
| `Construct_Remittance`, map `Payment_to_VendorRemittance` | Positional file body | Java transformer bean, then fixed-length marshal | H (see [D7](#d7-the-ledger-and-the-vendor-file-disagree-by-a-cent-on-pi-2026-880107)) |
| `Loop_Deliver`: **retry loop**, `while (!delivered && attempts < 3)` with an inner scope catching `DeliveryFailureException` and a **delay** of 10 min | Three attempts, ten minutes apart | `onException(DeliveryFailure).maximumRedeliveries(2).redeliveryDelay(600_000)` on the vendor step, or `loopDoWhile` with a counter if the attempt count must be visible | H (see D6) |
| `throw VendorUnreachableException` and the scope's **exception handler** with `compensate LedgerTx`, then `OpsMail.PaymentHeld(msgInstruction, attempts)` to `sp_Ops_PaymentHeld_SMTP` | Ledger post reversed, operations told | Saga failure triggers compensation; `doCatch`/`onCompletion(onFailureOnly)` sends the ops mail; `OpsMail` reimplemented in Java | H |

### `AdjusterAssignment.odx`

| Shape (XLANG/s) | What it does | Camel counterpart | Risk |
| --- | --- | --- | --- |
| `Receive_Request`, activating | From `FnolIntake` or from the claims system poll | `from("direct:adjusterAssignment")` plus the `sql:` poller feeding the same endpoint | M |
| `Parallel_Actions`: branch 1 map `AssignmentRequest_to_RosterQuery` + roster solicit-response; branch 2 archive to FILE | Both must finish before the notice | **Multicast** `multicast(strategy).parallelProcessing()` with both branches, `stopOnException()`; aggregation keeps the roster result and the request | M |
| `Construct_Notice`, two-source map `Roster_AssignmentRequest_to_Notice` | Least loaded eligible adjuster or escalation | Java transformer bean | M |
| `escalated = xpath(... Escalated)` | Read but never used afterwards | nothing (record it; do not invent a branch) | L |
| `Send_Notice` (SMTP) | Notice to adjuster or supervisor | `smtp:` with headers from the notice | L |

## 3. Maps (`Maps/`)

"Pure" means the `.btm` has links only, no functoids. Pure maps keep their XSLT and run from Camel's `xslt-saxon:` component; maps whose functoids carry logic become Java transformers held to the same goldens.

| Map | Pure or functoid | Functoids in the `.btm` | Target | Money and rounding to carry over | Corpus | Risk |
| --- | --- | --- | --- | --- | --- | --- |
| `CanonicalClaim_to_PolicyInqRq` | pure | none | keep XSLT | none | 16 | L |
| `AssignmentRequest_to_RosterQuery` | pure | none | keep XSLT | none | 10 | L |
| `Fnol_to_CanonicalClaim` | functoid | String Concatenate, String Extract, Value Mapping, Logical OR | Java | `EstimatedAmount` formatted `0.00` (`format-number`, half-even on the decimal) | 16 | L |
| `Claim_PolicyInqRs_to_InsertClaim` (two-source) | functoid | Less Than, Greater Than, Logical AND, Subtraction, Minimum, Value Mapping, Equal | Java | `NetExposure = max(min(estimate, limit) - deductible, 0)`; XSLT computes in `double` then `format-number(..., '0.00')`; Java in `BigDecimal` scale 2, `HALF_EVEN` at format | 16 | M |
| `InsertClaim_to_TriageFacts` | functoid, **2 C# scripting** | Scripting `ComputeReserve`, Scripting `DaysBetween` | Java | `HALF_EVEN` (.NET `Math.Round`) | 16 | M |
| `Payment_to_LedgerPost` | functoid, **2 C# scripting** | Scripting `MakeVendorReference`, Scripting `FormatMoney`, Cumulative Sum, Record Count | Java | `HALF_EVEN` (.NET `Math.Round`), invariant culture | 14 | M |
| `Payment_to_VendorRemittance` | functoid, **looping** | Looping, Record Count, Cumulative Sum, Multiplication, Round, Absolute Value, Value Mapping, String Find | Java | Per-line `round(abs(Amount) * 100)` kept as the source behaviour: `HALF_UP` on the absolute amount, in `BigDecimal` from the decimal text; trailer totals are the sum of the line cents | 14 | H (D7) |
| `Roster_AssignmentRequest_to_Notice` (two-source) | functoid | Equal, Less Than, Logical AND, Index, Value Mapping, String Concatenate, Iteration | Java | none (amount copied as text) | 10 | M |

### The two maps with C# scripting functoids

`InsertClaim_to_TriageFacts`:

- `ComputeReserve(estimatedAmount, lossCause, injuryFlag)`: factor by cause (COLL 1.10, COMP 1.00, GLAS 0.85, THFT 1.25, FIRE 1.40, WATR 1.30, WIND 1.15, LIAB 1.60, anything else including TOWG 1.00), plus 0.35 when `InjuryFlag == "true"`, then `Math.Round(estimate * factor, 2)` (half to even) and `ToString("0.00", InvariantCulture)`. Java: `estimate.multiply(factor).setScale(2, RoundingMode.HALF_EVEN)`. The corpus pins the midpoints: `CLM-2026-100405` 1002.50 x 1.25 = 1253.125 gives **1253.12**, `CLM-2026-100406` 2501.50 x 1.15 = 2876.725 gives **2876.72**; `HALF_UP` would give 1253.13 and 2876.73 and fail `make check`.
- `DaysBetween(from, to)`: `(int)(to - from).TotalDays` on `yyyy-MM-dd` dates; used for `ReportDelayDays` (loss to report) and `PolicyAgeDaysAtLoss` (effective to loss). Java: `ChronoUnit.DAYS.between`. Drives two triage rules (> 30 days, < 90 days).

`Payment_to_LedgerPost`:

- `MakeVendorReference(instructionId, claimNumber)`: claim number without hyphens plus the last six characters of the instruction id, upper-cased; append `00`, map letters A..Z to 10..35, mod 97 over the digit string, check = 98 - remainder, written `body-NN` (e.g. `CLM2026100405880107-76`). ISO 7064 mod 97-10 the IBAN way.
- `FormatMoney(amount)`: `Math.Round(Convert.ToDecimal(amount), 2)` then `0.00` invariant. Applied to the per-type sums: indemnity (`IND`), expense (`EXP`), salvage (`SLV`, negated so it reads as a positive credit) and net (signed sum of all lines). Java: `BigDecimal` sums, `setScale(2, HALF_EVEN)`. Note the compiled `.xslt` passes `string(sum(...))` of an XPath 1.0 `double` to the C#, while the `.golden.xslt` twin sums `xs:decimal`; for the corpus they agree (`PI-2026-880107`: 0.015 + 1234.565 = 1234.58), but the Java side should sum decimals, as the twin does. The ledger rounds the sum while the vendor file rounds each line, so `PI-2026-880107` posts 1235.08 and pays 1235.09 (D7).

### The looping functoid

`Payment_to_VendorRemittance`: the Looping functoid on `PaymentInstruction/Line` emits one `Payment` (PAY) record per line, with `LineNo`, the parent's `ClaimNumber`, `PayeeName` cut to 30 characters, `PayeeType`, `LineType`, `AmountCents = round(abs(Amount) * 100)` (each line rounded on its own, half toward positive infinity on the magnitude), `DebitCreditInd` `C` for negative lines and `D` otherwise, `ValueDate` without hyphens and `GLAccount`. Outside the loop, Record Count and a Cumulative Sum over the Round functoid's output fill the trailer: `PaymentCount`, `DebitTotalCents` and `CreditTotalCents` summed from the rounded line cents (the recursive `sumCents` template since `47ac76d`, so the trailer always agrees with the body), and `HashTotal = (debit + credit) mod 10^10` written with `format-number(..., '0')`. Since `24096535f` `AmountCents`, `DebitTotalCents` and `CreditTotalCents` also go through `format-number(..., '0')`, so no amount is written in exponent form (D1). Java: `amount.abs().movePointRight(2).setScale(0, RoundingMode.HALF_UP)` per line, `long` sums for the trailer.

## 4. Schemas (`Schemas/`)

| Schema | Root(s) | Kind | Promoted properties | Notes for the target |
| --- | --- | --- | --- | --- |
| `ACORD_ClaimsNotificationAddRq.xsd` | `ClaimsSvcRq` | document (ACORD FNOL) | `ClaimNumber`, `LossCauseCd`, `AgencyId` | Validated by the receive pipeline (`ValidateDocument=true`) |
| `FnolBatchEnvelope.xsd` | `FnolBatch` | **envelope** (`is_envelope="yes"`, `body_xpath` `/FnolBatch/Body`) | `AgencyId`, `BatchId` from `BatchHeader` | Camel `split(xpath("/FnolBatch/Body/*"))` copying header values to every part |
| `ACORD_PolicyInq.xsd` | `PolicyInqRq`, `PolicyInqRs` | **multi-root** (two roots, request and response) | none | JAXB or plain DOM |
| `Canonical_Claim.xsd` | `Claim` | canonical | `ClaimNumber` | |
| `ClaimsDb_InsertClaim.xsd` | `usp_InsertClaim` | WCF-SQL typed procedure | `ClaimNumber`, `TriageOutcome` | Does **not** promote `LossCauseCd`, which the glass filter needs (D3) |
| `TriageFacts.xsd` | `TriageFacts` | BRE fact document | **none** | Two filters subscribe on `TriageOutcome` for this type (D3) |
| `Canonical_PaymentInstruction.xsd` | `PaymentInstruction` | canonical | `ClaimNumber`, `PaymentVendorCd` | |
| `PaymentVendor_Remittance_FF.xsd` | `Remittance` | **flat file** (delimited CRLF postfix records, positional `HDR`/`PAY`/`TRL`, codepage 20127 US-ASCII) | none | Bindy `@FixedLengthRecord` or BeanIO; lengths, offsets, justification and pad chars from the `fieldInfo` annotations (`AmountCents` 12 right zero-padded at offset 57, `DebitCreditInd` at 69, trailer fields 6/14/14/10) |
| `ClaimsDb_LedgerPost.xsd` | `usp_PostClaimPayment` | WCF-SQL typed procedure | none | Same document posts and reverses; amounts are `xs:string` `0.00` |
| `AdjusterAssignment.xsd` | `AssignmentRequest`, `RosterQuery`, `RosterResult`, `AssignmentNotice` | **multi-root** (four roots) | `ClaimNumber`, `Region` (on `AssignmentRequest`) | |
| `PropertySchema.xsd` | 7 properties | property schema (`MessageContextPropertyBase`) | `ClaimNumber`, `LossCauseCd`, `AgencyId`, `BatchId`, `TriageOutcome`, `PaymentVendorCd`, `Region` | Become Camel headers; `NoticeTo`, `NoticeSubject`, `NoticeBody` used by the SMTP port are not defined here |

All instance documents use a qualified root and unqualified children (`elementFormDefault="unqualified"`); JAXB bindings or XPath in the Java code must keep that, or the goldens will not match.

## 5. Pipelines and components (`Pipelines/`)

| Pipeline | Stage | Component | Configuration | Rule it carries | Camel counterpart | Risk |
| --- | --- | --- | --- | --- | --- | --- |
| `FnolBatchReceivePipeline` (receive) | Decode | `PiiMaskingComponent` (custom, `Mask`) | `MaskedElementXPath=//*[local-name()='TaxId']`, `VisibleSuffixLength=4` | A full tax id never reaches the MessageBox, tracking or any port: every letter or digit except the last four becomes `X`, separators kept (`123-45-6789` to `XXX-XX-6789`) | Processor running first in the route, before the split, before any tracer, message history or log of the body | M (not covered by the corpus; long tail) |
| | Disassemble | XML disassembler | Envelope `FnolBatchEnvelope`, document `ACORD_ClaimsNotificationAddRq`, `AllowUnrecognizedMessage=false`, `ValidateDocument=true`, `RecoverableInterchangeProcessing=true` | One `ClaimsSvcRq` per message, header promoted onto each; an invalid FNOL is suspended alone, the rest of the batch goes on | `split()` with header copy, `validator:` per part, per-part error handler to a dead letter channel (`stopOnException=false`) | M |
| `VendorRemittanceSendPipeline` (send) | Assemble | Flat file assembler | `PaymentVendor_Remittance_FF`, US-ASCII (20127), no BOM | Fixed widths, space pad for text, zero pad for amounts, CRLF after every record | Bindy/BeanIO marshal with `charset=US-ASCII` | M |
| | Encode | `TrailerTotalsComponent` (custom, `Check`) | `FailOnMismatch=true` | Re-reads the file, recomputes `PaymentCount`, `DebitTotalCents`, `CreditTotalCents` and `HashTotal` from the PAY records, and suspends the message when the TRL disagrees | Processor after marshal that throws; the exchange goes to the dead letter channel and the saga compensates | H (all 14 goldens pass it since `24096535f`; D1) |

## 6. Business rules (`Rules/ClaimTriagePolicy.xml`, version 1.2, vocabulary `ClaimTriage` 1.2)

| Rule | Priority | Condition | Outcome | Reason appended | Claims in the corpus |
| --- | --- | --- | --- | --- | --- |
| `DeclineNotInForce` | 100 | `InForceAtLoss == false` | `DECLINE_NOT_IN_FORCE` | Policy not in force at loss date | 4 |
| `FraudFlagLateReport` | 90 | `ReportDelayDays > 30` | `FRAUD_REVIEW` | Reported more than 30 days after loss | 1 (`CLM-2026-100405`) |
| `FraudFlagNewPolicyLargeLoss` | 90 | `PolicyAgeDaysAtLoss < 90` and `EstimatedAmount > 5000.00` | `FRAUD_REVIEW` | Large loss within 90 days of inception | 1 (`CLM-2026-100413`) |
| `FraudFlagPriorHistory` | 90 | `PriorFraudFlag == true` | `FRAUD_REVIEW` | Claimant has a prior fraud flag | 1 (`CLM-2026-100410`) |
| `FastTrack` | 50 | `Outcome == ""`, `NetExposure <= 2500.00`, `InjuryFlag == false`, `InList(LossCause, "GLAS,TOWG,WIND")` | `FAST_TRACK` | Low exposure, no injury, fast-track cause | 4 |
| `LargeLoss` | 40 | `Outcome == ""`, `ReserveEstimate >= 50000.00` | `LARGE_LOSS` | Reserve at or above large-loss threshold | 1 (`CLM-2026-100408`) |
| `StandardHandling` | 10 | `Outcome == ""` | `STANDARD` | Standard handling | 4 |

Totals over 16 FNOLs: 4 declines, 3 fraud reviews, 4 fast tracks, 1 large loss, 4 standard (`corpus/golden/triage/SUMMARY.md`). The three fraud rules and the decline rule do not test for an empty outcome. `TriageFactsHelper.AddReason` and `TriageFactsHelper.InList` exist by name only. Camel/Java counterpart: a plain Java `ClaimTriagePolicy` bean (ordered rule list, thresholds from configuration matching the vocabulary literals), called with `.bean()`; a rules engine is not needed for seven rules.

## Divergences that need a decision

Each of these is a choice, not a bug fix; nothing in the plan picks an option until someone answers.

### D1. Resolved: vendor remittance goldens carried exponent-form amounts

Saxon runs the `version="1.0"` stylesheet with XPath 2.0+ number-to-string rules, so `value-of` on a `double` of one million cents or more came out as `1.112507E6`, and `tools/ff_render.py` padded that text into the positional fields; .NET `XslCompiledTransform` writes plain digits. Two fixture commits closed it: `47ac76d` totals the trailer from the rounded line cents and formats `HashTotal`, and `24096535f` writes `AmountCents`, `DebitTotalCents` and `CreditTotalCents` through `format-number(..., '0')`. Per-line rounding is unchanged and stays the source behaviour. Running `TrailerTotalsComponent.Check`'s logic over the 14 goldens at `24096535f`:

| Message | Sum of PAY debit cents | TRL `DebitTotalCents` | Sum of PAY credit cents | TRL `CreditTotalCents` | Difference | Verdict |
| --- | --- | --- | --- | --- | --- | --- |
| PI-2026-880100 | 966027 | 966027 | 104663 | 104663 | 0 | GREEN |
| PI-2026-880101 | 142948 | 142948 | 0 | 0 | 0 | GREEN |
| PI-2026-880102 | 1154046 | 1154046 | 0 | 0 | 0 | GREEN |
| PI-2026-880103 | 1063000 | 1063000 | 78247 | 78247 | 0 | GREEN |
| PI-2026-880104 | 912630 | 912630 | 0 | 0 | 0 | GREEN |
| PI-2026-880105 | 1033155 | 1033155 | 0 | 0 | 0 | GREEN |
| PI-2026-880106 | 753073 | 753073 | 34968 | 34968 | 0 | GREEN |
| PI-2026-880107 | 123509 | 123509 | 0 | 0 | 0 | GREEN |
| PI-2026-880108 | 1141819 | 1141819 | 0 | 0 | 0 | GREEN |
| PI-2026-880109 | 397890 | 397890 | 6560 | 6560 | 0 | GREEN |
| PI-2026-880110 | 1469282 | 1469282 | 0 | 0 | 0 | GREEN |
| PI-2026-880111 | 101199999 | 101199999 | 2500000 | 2500000 | 0 | GREEN |
| PI-2026-880112 | 742719 | 742719 | 23981 | 23981 | 0 | GREEN |
| PI-2026-880113 | 1051525 | 1051525 | 0 | 0 | 0 | GREEN |
| **Total** | **112151622** | **112151622** | **2748419** | **2748419** | **0** | **14 GREEN** |

`PaymentCount` and `HashTotal` match on all 14 as well, and no golden under `vendor-remittance/` or `vendor-remittance-ff/` contains exponent form. Nothing to decide; the cent between ledger and vendor on `PI-2026-880107` is a separate question (D7).

### D2. `FnolIntake` as exported does not do what `ESTATE.md` says

The `delay` branch still sits after the `listen` block's closing brace at `24096535f`. Read literally, the listen has one branch (wait for a correction, no timeout), the 15-minute delay then always runs, and `Construct_Canonical` rebuilds `msgClaim` from the original `msgFnol`, discarding the correction. (The other half of this item in the first draft, a `Call_Rules` that was only a comment, is resolved: `47ac76d` executes the policy in the `TriageTx` atomic scope.)

Option A: characterize from the intent in `ESTATE.md` and the shape comments (a listen with two branches). Option B: characterize the XLANG text as written. Recommendation: A, recording the defect in the characterization test's description, and confirm with whoever owns the BizTalk solution that the deployed assembly matches the intent.

### D3. The filter-only subscriptions have nothing to match in the export

- `sp_Fraud_Referral_FILE` and `sp_Declines_FILE` subscribe to `TriageFacts` with `TriageOutcome`, but `FnolIntake` never sends `msgTriageFacts` anywhere, `TriageFacts.xsd` promotes nothing, and on decline the orchestration terminates before any send.
- `sp_GlassVendor_FastTrack_SFTP` needs `LossCauseCd` on `usp_InsertClaim`, which `ClaimsDb_InsertClaim.xsd` does not promote (it is promoted on the FNOL only).

Option A: implement the routing the port descriptions and `ESTATE.md` describe (3 fraud, 4 declines, 2 glass in the corpus). Option B: reproduce the export, in which none of the three ports would receive anything. Recommendation: A; ask claims operations whether the fraud desk and agency liaison folders actually receive files today, because if they do, something outside this export (a direct-bound send, another application) publishes them and should be found.

### D4. BRE agenda semantics versus the reference evaluator

`tools/triage_reference.py` lets the first rule that sets `Outcome` win. Since `47ac76d` `FnolIntake` really executes the policy (`Policy.Execute`), so how the engine runs it is no longer academic. The policy has no `update` action, and the BRE does not re-evaluate conditions after an action changes a fact unless it is told to; every rule whose condition held at match time (with `Outcome` empty) fires in priority order, and the last writer wins. Read that way, `StandardHandling` (priority 10) would overwrite every outcome with `STANDARD`. I have not run this policy in the Business Rules Engine, so this needs confirming (Rules Composer test with one corpus fact, or production tracking data). Option A: keep the reference semantics (first writer wins; matches the policy's own description). Option B: reproduce BRE as executed. Recommendation: A, after the confirmation, because B would mean the deployed policy does not triage at all and the business would know.

### D5. Resolved: port maps duplicated the orchestrations' maps

In the first draft, `rp_ClaimsSystem_AssignmentRequest_WcfSql` applied `AssignmentRequest_to_RosterQuery` on receive, so it published a `RosterQuery` while `AdjusterAssignment` activates on an `AssignmentRequest`. `47ac76d` removed that inbound map and the outbound `CanonicalClaim_to_PolicyInqRq` on `sp_PolicyAdmin_PolicyInq_WcfSql`; both maps now run only inside the orchestrations. Nothing to decide.

### D6. Two retry layers and a service window on the vendor send

The orchestration retries 3 times 10 minutes apart on `DeliveryFailureException`; the send port itself retries 3 times 10 minutes apart and only opens 22:00 to 05:30. A delivery failure reaches the orchestration only after the port's retries are spent (up to 9 transport attempts), and a message outside the window waits instead of failing. Recommendation: one retry layer in Camel (the route's, 3 attempts, 10 minutes) plus the window as a route policy, and say in the saga's ops mail how many attempts were made; confirm the vendor's expectation of attempts per night.

### D7. The ledger and the vendor file disagree by a cent on PI-2026-880107

This decision belongs to the payment orchestration act (the `ClaimPayment` conversion in wave 2), not to the maps. Wave 1 pins each side to its own golden as the legacy hub produces it. `Payment_to_LedgerPost` sums the lines and rounds once (`HALF_EVEN`); `Payment_to_VendorRemittance` rounds each line (`HALF_UP` on the magnitude) and sums the cents. The legacy hub has no rule for the leftover cent, so the ledger and the vendor can disagree whenever a line has sub-cent precision. Over the corpus:

| Message | Ledger `NetAmount` | Vendor file net (PAY debits less credits) | Difference | Verdict |
| --- | --- | --- | --- | --- |
| PI-2026-880100 | 8613.64 | 8613.64 | 0.00 | GREEN |
| PI-2026-880101 | 1429.48 | 1429.48 | 0.00 | GREEN |
| PI-2026-880102 | 11540.46 | 11540.46 | 0.00 | GREEN |
| PI-2026-880103 | 9847.53 | 9847.53 | 0.00 | GREEN |
| PI-2026-880104 | 9126.30 | 9126.30 | 0.00 | GREEN |
| PI-2026-880105 | 10331.55 | 10331.55 | 0.00 | GREEN |
| PI-2026-880106 | 7181.05 | 7181.05 | 0.00 | GREEN |
| PI-2026-880107 | 1235.08 | 1235.09 | -0.01 | RED: lines 0.015 and 1234.565 round up one by one (2 and 123457 cents); the ledger rounds their sum 1234.580 |
| PI-2026-880108 | 11418.19 | 11418.19 | 0.00 | GREEN |
| PI-2026-880109 | 3913.30 | 3913.30 | 0.00 | GREEN |
| PI-2026-880110 | 14692.82 | 14692.82 | 0.00 | GREEN |
| PI-2026-880111 | 986999.99 | 986999.99 | 0.00 | GREEN |
| PI-2026-880112 | 7187.38 | 7187.38 | 0.00 | GREEN |
| PI-2026-880113 | 10515.25 | 10515.25 | 0.00 | GREEN |
| **Total** | **1,094,032.02** | **1,094,032.03** | **-0.01** | **13 GREEN, 1 RED** |

The options for that act, none chosen here: keep both sides as the legacy hub does and let the cent stand; post the vendor's per-line total to the ledger; or allocate the cent with an explicit rule both sides apply. Per-line rounding in the vendor file stays the source behaviour either way.

## Wave plan

Every wave pins first: goldens or characterization tests come from the legacy artefacts and are green before target code exists. `make check` stays the gate throughout; a converted unit passes when `make check` passes with its output in place of Saxon's (the runner needs a mode that compares a directory of target outputs with the goldens; adding it is the first commit of wave 1). No container is needed for waves 1 and 3; wave 2 needs PostgreSQL 16 for the aggregation and saga repositories and SFTP/SMTP stubs, all stopped at the end of each session.

### Wave 1: maps

Order and target:

1. `CanonicalClaim_to_PolicyInqRq`, `AssignmentRequest_to_RosterQuery`: keep the XSLT, run from `xslt-saxon:`.
2. `Fnol_to_CanonicalClaim`, `Claim_PolicyInqRs_to_InsertClaim`, `Roster_AssignmentRequest_to_Notice`: Java transformers.
3. `InsertClaim_to_TriageFacts`, `Payment_to_LedgerPost`: Java transformers for the C# scripting functoids, `HALF_EVEN`.
4. `Payment_to_VendorRemittance` and the fixed-length marshal: last, because it is the only map whose output also goes through a pipeline (flat file assembler and trailer guard).

What it proves against the corpus: all 112 map outputs match byte for byte with Java/Camel output in place of Saxon's (16 + 16 + 16 + 16 + 14 + 14 + 10 + 10), and the 14 positional files match. The numbers to watch: reserves 1253.12 and 2876.72 (`HALF_EVEN`); `PI-2026-880107` ledger 1235.08 (`HALF_EVEN` on the sum) and vendor body and trailer 123509 cents (`HALF_UP` per line), each held to its own golden, with the cent between them left to D7; vendor reference check digits on all 14 payments; `PI-2026-880111` net 986999.99 and salvage 25000.00.

### Wave 2: orchestrations

Order: `AdjusterAssignment` (multicast, lowest risk), `FnolIntake` (aggregator, enricher, router), `ClaimPayment` (saga, retry, compensation). Each starts with a characterization test written from the XLANG/s (after D2 for `FnolIntake`), red before the route exists. During this wave the `Call_Rules` step is satisfied from `corpus/golden/triage/*.json` behind the same interface the wave 3 policy implements, so the orchestration is tested alone.

What it proves against the corpus: the 16 FNOLs run end to end through the `FnolIntake` route with `corpus/stubs/policy/` answering the lookup, and the intermediate documents equal the `fnol-canonical`, `policy-inq-rq`, `insert-claim` and `triage-facts` goldens; 12 inserts are sent and 4 declines are not; 8 assignment requests are raised (12 minus 4 fast tracks). The 10 assignment requests run through `AdjusterAssignment` with `corpus/stubs/roster/`, matching `roster-query` and `assignment-notice` (8 assigned, 2 escalated to the supervisor), with an archive file for all 10. `ClaimPayment` starts with D7 answered. The 14 payments run through it, matching `ledger-post` and `vendor-remittance-ff`; with the vendor stub failing three times, the ledger reversal is sent with the identical document and one ops mail goes out. Characterization tests on top: a correction inside 15 minutes replaces the first FNOL, one after 15 minutes starts a new instance, and the aggregation window survives a restart.

### Wave 3: rules and routing

Order: `ClaimTriagePolicy` in Java (after D4 is confirmed), then the three filter-only subscriptions as router branches (after D3), then port-level routing (file names from `ClaimNumber` and `AgencyId`, ordered delivery on the insert, ledger and vendor sends, service windows).

What it proves against the corpus: the 16 triage results match `corpus/golden/triage/*.json` (outcome, reasons and rules fired) and `SUMMARY.md` (4 / 3 / 4 / 1 / 4). Routing assertions derived from those goldens: fraud desk gets exactly `CLM-2026-100405`, `100410`, `100413`; declines get `100403` and `100415` under `AG-0417`, `100407` under `AG-0922`, `100411` under `AG-1305`; the glass partner gets exactly `100400` and `100401`.

### Long tail (not covered by the corpus; each needs its goldens pinned before it moves)

- `PiiMaskingComponent.Mask` and the guarantee that no unmasked tax id is logged or traced. The corpus inputs are the unmasked agency messages (synthetic tax ids such as `100-40-7000`), so a converted masking step can run on them. But there is no golden of the masked message yet, and `fnol-canonical` masks through the map's own `***-**-` prefix, so pin a masked-output golden first.
- `FnolBatchEnvelope` debatching with `RecoverableInterchangeProcessing` and validation: no batch envelope in the corpus.
- `TrailerTotalsComponent.Check` as a guard: `make check` does not run it. The D1 table was produced by running its logic by hand; wave 1 should add it to the gate.
- Host key for `rl_Agency_FnolBatch_SFTP`: the binding has none, while both SFTP send ports pin an ed25519 fingerprint. The Camel consumer needs a `knownHostsFile` entry, so get the agency server's key from operations.
- Service windows: receive 22:00 to 06:00, vendor send 22:00 to 05:30; ordered delivery on three send ports.
- SMTP notice properties `NoticeTo`, `NoticeSubject`, `NoticeBody`: referenced by `sp_Adjuster_AssignmentNotice_SMTP`, not defined in `PropertySchema.xsd`, and nothing in `AdjusterAssignment.odx` sets them.
- Helpers referenced by name only: `AssignmentFactory.FromInsertClaim`, `OpsMail.PaymentHeld`, `TriageFactsHelper.AddReason` / `InList`.
- Vendor acknowledgement on the two-way SFTP port (`PassThruReceive`, `System.Xml.XmlDocument`): no ack sample in the corpus, and the vendor's ack contract needs confirming.
- Archive path macros `%Year%` and `%MessageID%`, and the seven-year retention.
- Failed message routing (`RouteFailedMessage=true` on all three receive ports) and the dead letter channel that replaces suspended messages.
- SFTP keys and SSO affiliates named in the bindings (`E:\Keys\*.ppk`), which do not exist in the fixture.
