"""Generate the inventory index and classified wave lanes from graph and decisions."""

import json
import re
from pathlib import Path


INVENTORY = Path(__file__).resolve().parents[1]
GROUNDWORK = """## Wave 0 — Groundwork (no processes)

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
"""


def parse_decisions(text):
    decisions = {}
    pattern = r'^## (D-\d\d) ([^\n]+)\n(.*?)(?=^## |\Z)'
    for match in re.finditer(pattern, text, re.M | re.S):
        identifier, title, body = match.groups()
        affected = re.search(r'^\*\*Affected processes:\*\* (.+)$', body, re.M)
        decision = re.search(
            r'^\*\*Decision:\*\*(.*?)(?=^\*\*[^*\n]+\*\*|^#{1,6}[ \t]|\Z)',
            body, re.M | re.S,
        )
        if not affected or not decision:
            raise ValueError(f'{identifier}: missing affected processes or decision field')
        if identifier in decisions:
            raise ValueError(f'duplicate decision: {identifier}')
        heading = f'{identifier} {title}'.lower()
        slug = re.sub(r'[^\w -]', '', heading).replace(' ', '-')
        decisions[identifier] = dict(
            title=title, slug=slug, processes=re.findall(r'`([^`]+)`', affected[1]),
            open=not decision[1].strip(),
        )
    return decisions


def decision_link(identifier, decisions):
    return f'[{identifier}](decisions.md#{decisions[identifier]["slug"]})'


def inventory_data(graph, decisions):
    processes = sorted((n for n in graph['nodes'] if n['type'] == 'process'), key=lambda n: n['id'])
    names = {p['label'] for p in processes}
    blockers = {name: [] for name in names}
    for identifier, decision in decisions.items():
        for name in decision['processes']:
            if name not in names:
                raise ValueError(f'{identifier}: unknown affected process {name}')
            if decision['open']:
                blockers[name].append(identifier)
    callers = {e['from'] for e in graph['edges'] if e['kind'] == 'call_process'}
    callees = {e['to'] for e in graph['edges'] if e['kind'] == 'call_process'}
    waves = {p['id']: 3 if p['id'] in callers else 2 if p['id'] in callees else 1 for p in processes}
    return processes, blockers, waves


def spec_link(process):
    domain, name = process['label'].split('.', 1)
    return f'[spec](specs/{domain}/{name}.md)'


def blocking_links(process, blockers, decisions):
    return ', '.join(decision_link(d, decisions) for d in sorted(blockers[process['label']]))


def classification(process, blockers):
    return 'needs-human-decision' if blockers[process['label']] else 'straight-conversion'


def wave_plan(graph, decisions):
    processes, blockers, waves = inventory_data(graph, decisions)
    output = [
        '# BW6 conversion wave plan', '',
        'Run **tib-d1111**. Scope: **24 processes**. Classification follows the remaining decisions; '
        'wave placement follows dependencies, not classification. Straight conversions can enter their '
        'wave after Wave 0; held flows enter only after their named decisions are resolved.', '',
        '## Ordering rule', '',
        'Convert callees before or together with callers. Call-process suffix matches are candidate '
        'bindings to verify in Wave 0. There are no in-project producer/consumer destination matches '
        'in [graph.json](graph.json); do not invent a queue pipeline. See [dependency graph](dependency-graph.md).', '',
        GROUNDWORK, '',
    ]
    for wave, title in ((1, 'Standalone leaf flows'), (2, 'Callees'), (3, 'Callers')):
        output.extend([f'## Wave {wave} — {title}', '',
                       '**Straight-conversion lane** (after Wave 0; callees with or before callers):', '',
                       '| Process | Classification | Decision IDs |',
                       '| --- | --- | --- |'])
        members = [p for p in processes if waves[p['id']] == wave and not blockers[p['label']]]
        for process in members:
            output.append(f'| `{process["label"]}` | straight-conversion | None |')
        if not members:
            output.extend(['', 'No straight-conversion processes in this wave.'])
        output.append('')
    output.extend(['## Held for decision', '',
                   'Target waves reserve ordering only; no held process is released by this plan.', '',
                   '| Process | Classification | Blocking decisions | Target wave |',
                   '| --- | --- | --- | --- |'])
    for process in processes:
        if blockers[process['label']]:
            output.append(f'| `{process["label"]}` | needs-human-decision | '
                          f'{blocking_links(process, blockers, decisions)} | Wave {waves[process["id"]]} |')
    output.extend(['', '## Wave summary', ''])
    for wave in (1, 2, 3):
        members = [p for p in processes if waves[p['id']] == wave]
        held = sum(bool(blockers[p['label']]) for p in members)
        output.append(f'- **Wave {wave}:** {len(members) - held} straight conversions; {held} held.')
    return '\n'.join(output) + '\n'


def readme(graph, decisions):
    processes, blockers, _ = inventory_data(graph, decisions)
    output = [
        '# BW6 source inventory', '',
        'Run **tib-d1111**; base commit **5c2ba511babbfacaba94c93a10d3e6b0542a7c4c**. '
        'This is a read-only inventory of the legacy export, not a conversion or a runtime certification. '
        'The export contains **24 .bwp files**. Classification and decision IDs are indexed below.', '',
        '## What is here', '',
        '- `specs/`: 24 per-process source inventories grouped by domain, plus domain READMEs; use the index below.',
        '- [graph.json](graph.json): source-derived nodes, edges, citations and computed dependency summary.',
        '- [dependency-graph.md](dependency-graph.md): generated Mermaid view, edge tables and graph findings.',
        '- [decisions.md](decisions.md): open questions, affected-process lists, source evidence and neutral options.',
        '- [wave-plan.md](wave-plan.md): programme-wide groundwork, straight-conversion lanes and held flows.',
        '- `tools/`: stdlib Python 3.10 generators, citation checks and unit tests. '
        'The README index and wave blockers are generated from graph.json and decisions.md.', '',
        'Run from the repository root:', '',
        '```sh',
        'python integration/inventory/bw6/tools/build_graph.py',
        'python integration/inventory/bw6/tools/build_inventory.py',
        'python integration/inventory/bw6/tools/check_citations.py',
        "python -m unittest discover -s integration/inventory/bw6/tools -p 'test_*.py'",
        'uv run --with ruff==0.9.10 ruff check integration',
        '```', '',
        'build_graph.py reads only the source estate and regenerates graph.json and dependency-graph.md. '
        'build_inventory.py reads graph.json and decisions.md, annotates process classification/decision IDs/waves in graph.json and regenerates this README and wave-plan.md; '
        'rerun it after affected-process lists change. Generated outputs stay under integration/inventory/bw6/. '
        'The tools do not change legacy source, corpus, target, harness or fixture files.', '',
        '## Reading a spec beside its source', '',
        'Open the spec and its .bwp from the index together, then follow the evidence #L anchors. '
        'Activity configurations occupy one line per activity: the starter is usually near L14 '
        '(instruction-intake uses L16); the fault-handler JMSConfirm is at L7. '
        'Do not infer execution order from the first activity declaration: the fault handler precedes '
        'the success sequence in the file.', '',
        'The section order is:', '',
        '1. Summary',
        '2. Trigger / starter activity',
        '3. Transports',
        '4. Transaction boundaries',
        '5. XSLT chain',
        '6. Custom Java activities',
        '7. Error paths',
        '8. Module properties per environment',
        '9. Callers and callees',
        '10. Reference evidence',
        '11. Conversion notes',
        '12. Cross-domain check (some specs use the unnumbered heading “Cross-domain check”).', '',
        'A citation label is a repo-root path plus one-based line or inclusive range: `path:L<n>` '
        'or `path:L<n>-L<m>`. The link target is relative to the containing Markdown file and repeats '
        'the line range in its fragment. Example: '
        '[`integration/legacy-bw6/Processes/payments/payment-returns.bwp:L14`]'
        '(../../legacy-bw6/Processes/payments/payment-returns.bwp#L14). '
        'Specs are two directories deeper, so their relative targets differ. '
        'The checker validates files and line ranges; it does not prove business intent or runtime behavior. '
        'Read **Inference** statements and [open decisions](decisions.md) alongside the quoted source.', '',
        '## Process index', '',
        'Blocking IDs are derived from each decision’s Affected processes list; all decisions remain open.', '',
        '| Process (declared name) | Domain | Spec link | .bwp link | Classification | Blocking decisions |',
        '| --- | --- | --- | --- | --- | --- |',
    ]
    for process in processes:
        path = process['file'].removeprefix('integration/')
        output.append(f'| `{process["id"]}` | {process["domain"]} | {spec_link(process)} | '
                      f'[.bwp](../../{path}#L2) | {classification(process, blockers)} | {blocking_links(process, blockers, decisions)} |')
    return '\n'.join(output) + '\n'


def main():
    graph = json.loads((INVENTORY / 'graph.json').read_text(encoding='utf-8'))
    decisions = parse_decisions((INVENTORY / 'decisions.md').read_text(encoding='utf-8'))
    processes, blockers, waves = inventory_data(graph, decisions)
    for process in processes:
        process.update(classification=classification(process, blockers),
                       decision_ids=blockers[process['label']], wave=waves[process['id']])
    (INVENTORY / 'graph.json').write_text(json.dumps(graph, indent=2) + '\n', encoding='utf-8')
    (INVENTORY / 'wave-plan.md').write_text(wave_plan(graph, decisions), encoding='utf-8')
    (INVENTORY / 'README.md').write_text(readme(graph, decisions), encoding='utf-8')
    processes, blockers, waves = inventory_data(graph, decisions)
    counts = {wave: sum(value == wave for value in waves.values()) for wave in (1, 2, 3)}
    print(f'generated wave-plan.md and README.md: {len(processes)} processes, '
          f'{sum(bool(ids) for ids in blockers.values())} held; wave slots {counts}')


if __name__ == '__main__':
    main()
