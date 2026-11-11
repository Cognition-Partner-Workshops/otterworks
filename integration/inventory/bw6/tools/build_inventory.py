"""Generate the inventory index and held wave slots from graph and decision data."""

import json
import re
from pathlib import Path


INVENTORY = Path(__file__).resolve().parents[1]
CLASSIFICATION = 'needs-human-decision'


def parse_decisions(text):
    decisions = {}
    pattern = r'^## (D-\d\d) ([^\n]+)\n(.*?)(?=^## |\Z)'
    for match in re.finditer(pattern, text, re.M | re.S):
        identifier, title, body = match.groups()
        affected = re.search(r'^\*\*Affected processes:\*\* (.+)$', body, re.M)
        decision = re.search(r'^\*\*Decision:\*\*[^\S\n]*(.*)$', body, re.M)
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


def wave_plan(graph, decisions):
    processes, blockers, waves = inventory_data(graph, decisions)
    def gates(ids):
        return ', '.join(decision_link(d, decisions) for d in ids)
    output = [
        '# BW6 conversion wave plan', '',
        'Run **tib-d1111**. This is a conditional ordering plan, not approval to convert or release. '
        'All 24 processes are classified **needs-human-decision** and remain in the **Held for decision** lane. '
        'Every wave is currently empty of releasable processes; its members are only **planned (currently held)** slots.', '',
        '## Ordering rule', '',
        'Put shared-resource and property groundwork first. Convert callees and producers before or together '
        'with their callers and consumers. The source-derived [graph.json](graph.json) summary has no '
        'in-project producer→consumer destination matches, so this ordering is driven by call_process edges '
        'and shared resources, not an assumed queue pipeline. See the [dependency graph](dependency-graph.md). '
        'Call edges remain unresolved name bindings until D-04 is decided. Any flow blocked by an open '
        'decision stays held, even when its proposed wave is reached.', '',
        'Blocking IDs below are generated from the **Affected processes** lists in [decisions.md](decisions.md), '
        'not independently assigned. Every process includes open D-09, D-11, D-23 and D-24, plus its other '
        'listed decisions. D-25 scope confirmation also affects every process. Wave-wide entry gates can '
        'be stricter than a process’s own blocker list.', '',
        '## Wave 0 — Groundwork (no processes)', '',
        '**Slot members:** no processes. Groundwork is planned (currently held):', '',
        '- [EmsConnection](../../legacy-bw6/SharedResources/EmsConnection.sharedresource), '
        '[LedgerJdbc](../../legacy-bw6/SharedResources/LedgerJdbc.sharedresource), '
        '[ServiceHttp](../../legacy-bw6/SharedResources/ServiceHttp.sharedresource), '
        '[StatementSftp](../../legacy-bw6/SharedResources/StatementSftp.sharedresource).',
        '- screening.url, billing.url, files.url and notifications.url properties in '
        '[dev](../../legacy-bw6/Profiles/dev.substvar) and [prod](../../legacy-bw6/Profiles/prod.substvar), '
        'plus the EMS, DB and SFTP credential/host supply contracts.',
        f'- The {sum(n["type"] == "table" for n in graph["nodes"])} tables in '
        '[Database/schema.sql](../../legacy-bw6/Database/schema.sql).',
        '- [Transforms/common/receipt.xsl](../../legacy-bw6/Transforms/common/receipt.xsl), '
        'including payment-status → payments/status-policy → payments/base/clearing-policy → common/receipt '
        'and statement → statements/layout → statements/base/timezone → common/receipt import chains.',
        '- [FeeActivities Java](../../legacy-bw6/src/com/halvergate/integration/FeeActivities.java) '
        'state/rounding contracts and HB.UNDLV ownership, monitoring, drain and replay handling.', '',
        '**Entry criteria:** ' + gates(['D-01', 'D-02', 'D-03', 'D-11', 'D-12', 'D-23', 'D-24'])
        + ' decided, and ' + gates(['D-25']) + ' scope confirmed.', '',
        '**Exit criteria:** approved shared configuration and schema are in the target; receipt-transform '
        'parity is demonstrated on the reference inputs under the approved namespace and output contract. '
        'No conversion or parity execution is performed by this inventory.', '',
        '**Current status:** 0 releasable processes; groundwork is held for its entry decisions.', '',
    ]
    headings = {1: 'Standalone leaf flows', 2: 'Callees', 3: 'Callers'}
    criteria = {
        1: 'Wave 0 exit criteria met and each flow’s blocking decisions decided.',
        2: 'Wave 0 exit criteria met, ' + gates(['D-04']) + ' decided, and each flow’s blocking decisions decided.',
        3: 'Their Wave-2 callees’ entry criteria met, ' + gates(['D-04', 'D-09'])
        + ' decided (including the transaction boundary across caller/callees), and each caller’s blocking '
        'decisions decided. Convert each caller together with or after all of its callees.',
    }
    for wave in (1, 2, 3):
        output.extend([f'## Wave {wave} — {headings[wave]}', '', '**Slot members (planned (currently held)):**', ''])
        members = [p for p in processes if waves[p['id']] == wave]
        for process in members:
            suffix = ''
            if wave == 3:
                callees = sorted(e['to'].removeprefix('halvergate.') for e in graph['edges']
                                 if e['kind'] == 'call_process' and e['from'] == process['id'])
                suffix = '; together with or after ' + ', '.join(f'`{c}`' for c in callees)
            output.append(f'- `{process["label"]}` — planned (currently held){suffix}.')
        if wave == 1:
            output.extend(['', 'These nine leaf flows have no incoming or outgoing call_process edges.'])
        if wave == 2:
            output.extend(['', 'Twelve callees: four each in account-events, payments and statements-documents.'])
        output.extend(['', '**Entry criteria:** ' + criteria[wave], '',
                       '**Current status:** 0 releasable processes; every listed slot remains held.', ''])
    output.extend([
        '## Held for decision', '',
        '| Process | Domain | Spec link | Classification | Blocking decisions | Target wave once released |',
        '| --- | --- | --- | --- | --- | --- |',
    ])
    for process in processes:
        output.append(f'| `{process["label"]}` | {process["domain"]} | {spec_link(process)} | '
                      f'{CLASSIFICATION} | {blocking_links(process, blockers, decisions)} | Wave {waves[process["id"]]} |')
    output.extend(['', '## Wave summary', '',
                   '- **Wave 0:** groundwork only; no process slots; 0 releasable processes.'])
    for wave in (1, 2, 3):
        count = sum(value == wave for value in waves.values())
        output.append(f'- **Wave {wave}:** {count} {headings[wave].lower()} planned (currently held); 0 releasable processes.')
    return '\n'.join(output) + '\n'


def readme(graph, decisions):
    processes, blockers, _ = inventory_data(graph, decisions)
    output = [
        '# BW6 source inventory', '',
        'Run **tib-d1111**; base commit **5c2ba511babbfacaba94c93a10d3e6b0542a7c4c**. '
        'This is a read-only inventory of the legacy export, not a conversion or a runtime certification. '
        'All 24 processes are **needs-human-decision** and currently held. Although the run brief expected '
        '25 .bwp files, only 24 exist in the export; '
        + decision_link('D-25', decisions) + ' leaves scope confirmation open.', '',
        '## What is here', '',
        '- `specs/`: 24 per-process source inventories grouped by domain, plus domain READMEs; use the index below.',
        '- [graph.json](graph.json): source-derived nodes, edges, citations and computed dependency summary.',
        '- [dependency-graph.md](dependency-graph.md): generated Mermaid view, edge tables and graph findings.',
        '- [decisions.md](decisions.md): open questions, affected-process lists, source evidence and neutral options.',
        '- [wave-plan.md](wave-plan.md): groundwork and conditional process slots, with all flows held.',
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
        'build_inventory.py reads graph.json and decisions.md and regenerates this README and wave-plan.md; '
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
                      f'[.bwp](../../{path}#L2) | {CLASSIFICATION} | {blocking_links(process, blockers, decisions)} |')
    return '\n'.join(output) + '\n'


def main():
    graph = json.loads((INVENTORY / 'graph.json').read_text(encoding='utf-8'))
    decisions = parse_decisions((INVENTORY / 'decisions.md').read_text(encoding='utf-8'))
    (INVENTORY / 'wave-plan.md').write_text(wave_plan(graph, decisions), encoding='utf-8')
    (INVENTORY / 'README.md').write_text(readme(graph, decisions), encoding='utf-8')
    processes, blockers, waves = inventory_data(graph, decisions)
    counts = {wave: sum(value == wave for value in waves.values()) for wave in (1, 2, 3)}
    print(f'generated wave-plan.md and README.md: {len(processes)} processes, '
          f'{sum(bool(ids) for ids in blockers.values())} held; wave slots {counts}')


if __name__ == '__main__':
    main()
