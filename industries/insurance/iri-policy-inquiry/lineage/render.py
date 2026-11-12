import argparse
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parent


def render(entries):
    lines = ['# Policy Inquiry lineage', '', 'Generated from `lineage.yaml`; edit the YAML, not this table.', '']
    def cell(value):
        return str(value if value is not None else '—').replace('|', '\\|').replace('\n', ' ')
    for operation in ('summary', 'values', 'funds'):
        lines += [f'## {operation}', '', '| DB column | legacy field (format) | IRI element (type/constraint) | rule | status | sign-off |', '| --- | --- | --- | --- | --- | --- |']
        for e in entries:
            if e['operation'] != operation:
                continue
            rule = e['rule']
            if 'scale' in e:
                rule += f"({e['scale']})"
            if 'map' in e:
                rule += ' ' + ', '.join(f'{k}→{v}' for k, v in e['map'].items())
            if 'item_rule' in e:
                rule += ' / ' + e['item_rule']
            target = ', '.join(e.get('targets', [e['iri_element'] or ('HTTP status' if e['legacy_field'] == 'RTN_CD' else '—')]))
            values = [e['db'], f"{e['legacy_field'] or 'no source'} ({e['legacy_format']})", f"{target} ({e['iri_type_constraint']})", rule, e['status'], e['signoff_id']]
            lines.append('| ' + ' | '.join(map(cell, values)) + ' |')
        lines.append('')
        for e in entries:
            if e['operation'] == operation and e['note']:
                lines.append(f"- `{e['legacy_field'] or e['iri_element']}`: {e['note']}.")
        lines.append('')
    lines += ['## IRI required elements with no legacy source', '']
    for e in entries:
        if e['legacy_field'] is None:
            lines.append(f"- {e['operation']} `{e['iri_element']}`: {e['note']} ({e['signoff_id']}).")
    lines += ['', '## Sign-off list', '']
    for signoff in sorted({e['signoff_id'] for e in entries if e['signoff_id']}):
        notes = list(dict.fromkeys(e['note'] for e in entries if e['signoff_id'] == signoff))
        lines.append(f"- **{signoff}**: " + '; '.join(notes) + '.')
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    content = render(yaml.safe_load((ROOT / 'lineage.yaml').read_text())['entries'])
    output = ROOT / 'LINEAGE.md'
    if args.check:
        if not output.exists() or output.read_text() != content:
            parser.exit(1, 'LINEAGE.md is out of sync\n')
        print('LINEAGE.md is in sync')
    else:
        output.write_text(content)
        print(f'Generated {output}')


if __name__ == '__main__':
    main()
