# Claims intake and payment hub (BizTalk Server 2016 solution, as exported)

This directory is the BizTalk side of the carrier's claims hub, kept as the artefacts a BizTalk developer would have in Visual Studio plus the behaviour corpus a migration is measured against. Nothing here needs BizTalk Server or Windows: the maps' compiled XSLT runs under Saxon, the flat-file layout is rendered from the schema, and the rules policy is evaluated by a reference script. The names in this file are fixed; changing one changes this file in the same commit.

The hub connects three parties: agencies, which send first notices of loss over SFTP every night; the claims system and its ledger, reached through WCF-SQL typed procedures; and payment vendors, which take a positional remittance file over SFTP and are told about adjuster assignments by mail.

## How to run

```bash
make deps      # saxonche and PyYAML from tools/xslt-golden/requirements.txt
make check     # the gate: 112 map outputs, 14 positional files and 16 triage results must match byte for byte
make golden    # regenerate every golden after a deliberate change to a map, a schema or the policy
```

`make check` is what `.github/workflows/insurance-biztalk-corpus.yml` runs on every pull request that touches this directory or `tools/xslt-golden`.

## Orchestrations (`Orchestrations/`)

| File | Service | Shapes that carry behaviour | Business rule |
| --- | --- | --- | --- |
| `FnolIntake.odx` | `FnolIntake` | Activating receive that initialises `ClaimNumberCorrelation`; a Listen with a correlated receive and a 15 minute Delay; two-source transform; Call Rules on `ClaimTriage`; Decide on the outcome; Terminate on decline | A corrected FNOL for the same claim number inside 15 minutes replaces the first one; after the window it is a new instance and the claims system rejects the duplicate. Declined policies are never inserted. Fast-track claims skip adjuster assignment. |
| `ClaimPayment.odx` | `ClaimPayment` | Long-running scope `PaymentTx` around an atomic scope `LedgerTx` with a compensation block; a retry loop (three attempts, ten minutes apart) against the vendor service window; exception handler that calls `compensate LedgerTx` and mails operations | The ledger post happens before the vendor file goes out; if the vendor cannot be reached after three attempts the post is reversed with the same document and operations is told. A payment is never on the ledger without a remittance file, and never in a file without a ledger post. |
| `AdjusterAssignment.odx` | `AdjusterAssignment` | Parallel shape: branch one maps the request to a roster query and calls WCF-SQL, branch two archives the request to FILE; two-source transform; SMTP send | Both branches finish before the notice goes, so the archive copy exists for every request, including the escalated ones. The least loaded eligible adjuster is chosen, ties broken by id; with nobody eligible the notice escalates to the supervisor address. |

## Maps (`Maps/`)

Each map is a `.btm` (the Mapper's own file) and the `.xslt` it compiles to. Two maps embed inline C# in `msxsl:script`; Saxon cannot run that, so each has a `.golden.xslt` twin with the C# translated into XSLT 3.0 functions, and the twin is what the manifest runs. The twins carry .NET semantics the Java side must reproduce: `Math.Round` rounds half to even, and amounts are formatted with the invariant culture.

| Map | Source | Target | Functoids | Business rule |
| --- | --- | --- | --- | --- |
| `Fnol_to_CanonicalClaim` | `ACORD_ClaimsNotificationAddRq` | `Canonical_Claim` | String Concatenate, String Extract, Value Mapping, Logical OR | Tax id is masked to its last four characters; `PriorFraudFlag` and `PoliceReport` default to false when the agency omits them; the estimate is normalised to two decimals. |
| `CanonicalClaim_to_PolicyInqRq` | `Canonical_Claim` | `ACORD_PolicyInq` (`PolicyInqRq`) | none | The policy is looked up as of the loss date (the report date can be weeks later). |
| `Claim_PolicyInqRs_to_InsertClaim` | `Canonical_Claim` and `PolicyInqRs` (two-source) | `ClaimsDb_InsertClaim` | Less Than, Greater Than, Logical AND, Subtraction, Minimum, Value Mapping, Equal | `NetExposure` is the estimate capped at the coverage limit less the deductible, floored at zero. `InForceAtLoss` needs status Active and a loss date inside the effective and expiration dates. `TriageOutcome` is emitted nil and filled by the orchestration. |
| `InsertClaim_to_TriageFacts` | `ClaimsDb_InsertClaim` | `TriageFacts` | Scripting (C#) `ComputeReserve`, Scripting (C#) `DaysBetween` | Reserve is the estimate times a factor per loss cause (COLL 1.10, COMP 1.00, GLAS 0.85, THFT 1.25, FIRE 1.40, WATR 1.30, WIND 1.15, LIAB 1.60, other 1.00) plus 0.35 when anyone was hurt, rounded half to even to cents. Report delay and policy age are whole days. |
| `Payment_to_VendorRemittance` | `Canonical_PaymentInstruction` | `PaymentVendor_Remittance_FF` | Looping, Record Count, Cumulative Sum, Multiplication, Round, Absolute Value, Value Mapping, String Find | One PAY record per payment line; amounts in absolute cents (each line rounded on its own) with a D or C indicator (negative lines are credits); the trailer carries the record count, the debit and credit totals summed from the rounded line cents, and a hash that is their sum modulo ten billion. Payee names are cut at 30 characters. |
| `Payment_to_LedgerPost` | `Canonical_PaymentInstruction` | `ClaimsDb_LedgerPost` | Scripting (C#) `MakeVendorReference`, Scripting (C#) `FormatMoney`, Cumulative Sum, Record Count | The vendor reference is the claim number without hyphens plus the last six characters of the instruction id, upper-cased, with two ISO 7064 mod 97-10 check digits computed over the IBAN letter mapping. Indemnity, expense and salvage are summed per line type before rounding, salvage reported as a positive credit, net is the signed sum; all formatted `0.00`. Because the vendor file rounds per line and the ledger rounds the sum, an instruction with sub-cent lines (`PI-2026-880107`) posts 1235.08 to the ledger and sends 1235.09 to the vendor; the legacy hub has no allocation rule for that cent, and the migration must raise it as a decision rather than pick a side. |
| `AssignmentRequest_to_RosterQuery` | `AdjusterAssignment` (`AssignmentRequest`) | `AdjusterAssignment` (`RosterQuery`) | none | Roster is queried by region and required skill as of the request date. |
| `Roster_AssignmentRequest_to_Notice` | `RosterResult` and `AssignmentRequest` (two-source) | `AdjusterAssignment` (`AssignmentNotice`) | Equal, Less Than, Logical AND, Index, Value Mapping, String Concatenate, Iteration | Eligible means available, same region, skill present in the comma-separated list, open claims below the maximum. Lowest open claims wins, then lowest id. SLA is 1, 3 or 7 days for HIGH, MED and LOW. No eligible adjuster escalates to `claims.supervisor@thistlecombe.example`. |

## Schemas (`Schemas/`)

| File | Root(s) | Kind | Notes |
| --- | --- | --- | --- |
| `ACORD_ClaimsNotificationAddRq.xsd` | `ClaimsSvcRq` | ACORD P&C style FNOL | Promotes `ClaimNumber`, `LossCauseCd`, `AgencyId`. |
| `ACORD_PolicyInq.xsd` | `PolicyInqRq`, `PolicyInqRs` | ACORD style policy lookup | Response carries status, dates, deductible, limit and coverages. |
| `FnolBatchEnvelope.xsd` | `FnolBatch` | Envelope | `Body` is the body xpath; the disassembler debatches one `ClaimsSvcRq` per message and promotes `BatchId` and `AgencyId` onto each. |
| `Canonical_Claim.xsd` | `Claim` | Canonical | The hub's own claim shape. |
| `ClaimsDb_InsertClaim.xsd` | `usp_InsertClaim` | WCF-SQL typed procedure | Promotes `ClaimNumber` and `TriageOutcome`. |
| `TriageFacts.xsd` | `TriageFacts` | Rules fact document | `Outcome` and `Reason` are written by the policy. |
| `Canonical_PaymentInstruction.xsd` | `PaymentInstruction` | Canonical | Promotes `ClaimNumber` and `PaymentVendorCd`. |
| `PaymentVendor_Remittance_FF.xsd` | `Remittance` | Positional flat file | `HDR`, `PAY` (repeating) and `TRL` records, CRLF after each; field widths and padding in the `fieldInfo` annotations. `tools/ff_render.py` reads them to render the text files. |
| `ClaimsDb_LedgerPost.xsd` | `usp_PostClaimPayment` | WCF-SQL typed procedure | The same document is sent to post and to reverse. |
| `AdjusterAssignment.xsd` | `AssignmentRequest`, `RosterQuery`, `RosterResult`, `AssignmentNotice` | Multi-root | Promotes `ClaimNumber` and `Region`. |
| `PropertySchema.xsd` | property schema | Context properties | `ClaimNumber`, `LossCauseCd`, `AgencyId`, `BatchId`, `TriageOutcome`, `PaymentVendorCd`, `Region`. |

All instance documents follow the BizTalk convention: a namespace-qualified root and unqualified children (`elementFormDefault="unqualified"`).

## Pipelines (`Pipelines/`)

| File | Direction | Components | Business rule |
| --- | --- | --- | --- |
| `FnolBatchReceivePipeline.btp` | receive | `PiiMaskingComponent` (Decode), XML disassembler with `FnolBatchEnvelope` (Disassemble) | A full tax id never reaches the MessageBox, tracking or any send port: the component rewrites it to `XXX-XX-nnnn` before debatching. The corpus inputs are the unmasked agency messages, so a converted pipeline is tested on what it receives. |
| `VendorRemittanceSendPipeline.btp` | send | Flat file assembler, `TrailerTotalsComponent` (Encode) | The assembled file is re-read and its trailer recomputed from the PAY records; a mismatch suspends the message instead of sending the vendor a file they will reject. |

The two components are in `Pipelines/Components/` as C# source. Their static methods (`PiiMaskingComponent.Mask`, `TrailerTotalsComponent.Check`) are the behaviour; the interface plumbing is BizTalk's.

## Rules (`Rules/`)

`ClaimTriagePolicy.xml` is the `ClaimTriage` policy, version 1.2, and `ClaimTriageVocabulary.xml` the vocabulary it is written against. Rules fire by priority; the first to set `Outcome` wins because the lower rules test for an empty outcome; every fired rule appends a reason.

| Rule | Priority | Condition | Outcome |
| --- | --- | --- | --- |
| `DeclineNotInForce` | 100 | `InForceAtLoss` is false | `DECLINE_NOT_IN_FORCE` |
| `FraudFlagLateReport` | 90 | `ReportDelayDays` > 30 | `FRAUD_REVIEW` |
| `FraudFlagNewPolicyLargeLoss` | 90 | `PolicyAgeDaysAtLoss` < 90 and `EstimatedAmount` > 5000.00 | `FRAUD_REVIEW` |
| `FraudFlagPriorHistory` | 90 | `PriorFraudFlag` is true | `FRAUD_REVIEW` |
| `FastTrack` | 50 | no outcome yet, `NetExposure` <= 2500.00, no injury, cause in GLAS, TOWG, WIND | `FAST_TRACK` |
| `LargeLoss` | 40 | no outcome yet, `ReserveEstimate` >= 50000.00 | `LARGE_LOSS` |
| `StandardHandling` | 10 | no outcome yet | `STANDARD` |

Over the 16 FNOL messages the policy yields 4 declines, 3 fraud reviews, 4 fast tracks, 1 large loss and 4 standard claims (`corpus/golden/triage/SUMMARY.md`).

## Bindings (`Bindings/ClaimsHub.BindingInfo.xml`)

| Port | Transport | Direction | Purpose |
| --- | --- | --- | --- |
| `rp_Agency_FnolBatch_SFTP` | SFTP | receive | Nightly agency batches, service window 22:00 to 06:00, `FnolBatchReceivePipeline`. |
| `rp_ClaimsSystem_PaymentInstruction_FILE` | FILE | receive | Payment instructions from the disbursement job. |
| `rp_ClaimsSystem_AssignmentRequest_WcfSql` | WCF-SQL typed polling | receive | Assignment requests raised by desk adjusters. |
| `sp_PolicyAdmin_PolicyInq_WcfSql` | WCF-SQL | solicit-response | `usp_GetPolicyAsOf`. |
| `sp_ClaimsDb_InsertClaim_WcfSql` | WCF-SQL | send | `usp_InsertClaim`, ordered delivery, ambient transaction. |
| `sp_ClaimsDb_LedgerPost_WcfSql` | WCF-SQL | send | `usp_PostClaimPayment`, no retries (the orchestration owns the retry and the compensation). |
| `sp_ClaimsDb_RosterQuery_WcfSql` | WCF-SQL | solicit-response | `usp_GetAdjusterRoster`. |
| `sp_PaymentVendor_Remittance_SFTP` | SFTP | solicit-response | Vendor inbox, service window 22:00 to 05:30, `VendorRemittanceSendPipeline`, public key authentication. |
| `sp_Adjuster_AssignmentNotice_SMTP` | SMTP | send | To, subject and body come from the message's promoted properties. |
| `sp_Ops_PaymentHeld_SMTP` | SMTP | send | Operations mailbox for held payments. |
| `sp_Compliance_AssignmentArchive_FILE` | FILE | send | Seven-year archive of assignment requests. |

Three send ports have no orchestration behind them; they are content-based subscriptions on the MessageBox and the migration must reproduce them as routing:

| Port | Filter | Target |
| --- | --- | --- |
| `sp_Fraud_Referral_FILE` | message type `TriageFacts` and `TriageOutcome` = `FRAUD_REVIEW` | fraud desk folder |
| `sp_Declines_FILE` | message type `TriageFacts` and `TriageOutcome` = `DECLINE_NOT_IN_FORCE` | agency liaison folder, per agency |
| `sp_GlassVendor_FastTrack_SFTP` | message type `usp_InsertClaim`, `TriageOutcome` = `FAST_TRACK`, `LossCauseCd` = `GLAS` | glass network partner |

## Behaviour corpus (`corpus/`)

`corpus/generate.py` writes the inputs deterministically; `corpus/manifest.yaml` tells `tools/xslt-golden` which map runs over which directory and where the goldens live.

| Directory | Count | What |
| --- | --- | --- |
| `inputs/fnol/` | 16 | FNOL messages as the agency sent them, before `PiiMaskingComponent` runs (synthetic tax ids, so the masking rule can be tested end to end), one per claim `CLM-2026-100400` to `CLM-2026-100415`. Includes a 33 day late report, a claimant with a prior fraud flag, a loss 20 days into a new policy, two midpoint reserve cases (1002.50 at 1.25 and 2501.50 at 1.15) and four policies not in force. |
| `inputs/payment/` | 14 | Payment instructions `PI-2026-880100` to `PI-2026-880113`. `880107` carries sub-cent amounts (0.015 and 1234.565); `880111` is a 999999.99 large loss with a 25000.00 salvage credit. |
| `inputs/assignment/` | 10 | Assignment requests `ASG-520100` to `ASG-520109` across three regions and five skills; two of them find nobody eligible. |
| `stubs/policy/`, `stubs/roster/` | 16, 10 | What the WCF-SQL ports answer. |
| `inputs/fnol-enriched/`, `inputs/assignment-enriched/` | 16, 10 | The two-part aggregate documents BizTalk builds for its multi-source maps (derived, committed so the maps run without an orchestration). |
| `golden/<map>/` | 112 | One output per map per input, written by Saxon. |
| `golden/vendor-remittance-ff/` | 14 | The positional text files the flat file assembler produces, rendered from the schema. |
| `golden/triage/` | 16 and a summary | The policy's outcome, reasons and fired rules per claim. |

Forty primary input messages across three flows make the goldens the contract: a Camel route, an XSLT or a Java transformer that replaces a map is done when `make check` passes with its output in place of Saxon's.

## Boundaries of the fixture

No BizTalk Server, no Windows host, no deployment scripts, no SSO affiliate secrets (the binding file names key files that do not exist here). The helpers the orchestrations call (`AssignmentFactory`, `OpsMail`, `TriageFactsHelper`) are referenced by name only; their behaviour is described in the orchestration comments and the vocabulary.
