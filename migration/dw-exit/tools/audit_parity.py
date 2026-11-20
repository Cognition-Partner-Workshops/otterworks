"""Render audit evidence using the billing PR's row-linked parity table format."""
import argparse
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[3]


def render(text, branch):
    board = json.loads(text)
    summary = board['summary']['audit']
    base = 'https://github.com/Cognition-Partner-Workshops/otterworks/blob/' + quote(branch, safe='/') + '/'
    lines = ['# Audit parity — all 57 objects', '',
        f"Run sfg1120 (RUN_TOKEN=sfx-sfg1120). Local DuckDB: **{summary['local_green']} green / {summary.get('local_approved_deviation',0)} approved deviations / {summary.get('local_retired',0)} retired / {summary['local_red']} red**. "
        + 'Snowflake: **red** — ' + summary['snowflake_reason'] + '.', '',
        'Spark compares actual legacy lake and JDBC outputs against shipped dbt models on the same landing PSVs. '
        'Batch and isolated PowerCenter runs are separate evidence paths. '
        'Six owner-approved retirements carry DBQL evidence. Local evidence is not live Snowflake proof.', '',
        '| Object | Rows before/after | Profile diffs | Hash Δ | DuckDB | Snowflake | Board row and provenance |',
        '|---|---:|---:|---:|---|---|---|']
    start = re.search(r'^  "rows": \[', text, re.M)
    if start is None:
        raise ValueError('Expected indented board rows array')
    offset = text.index('[', start.start()) + 1
    decoder = json.JSONDecoder()
    while True:
        while offset < len(text) and text[offset] in ' \n\r\t,':
            offset += 1
        if text[offset] == ']':
            break
        row, end = decoder.raw_decode(text, offset)
        if row['subject_area'] == 'audit':
            first, last = text.count('\n', 0, offset) + 1, text.count('\n', 0, end) + 1
            counts = row.get('row_count')
            counts = f"{counts['before']}/{counts['after']}" if counts else '—'
            profiles = row.get('column_profile')
            diffs = sum(values['before'].get(column) != values['after'].get(column)
                        for values in profiles.values()
                        for column in values['before'].keys() | values['after'].keys()) if profiles is not None else '—'
            hashes = row.get('keyed_row_hash')
            delta = sum(value['difference'] for value in hashes.values()) if hashes is not None else '—'
            evidence = base + f'migration/dw-exit/board/board.json#L{first}-L{last}'
            lines.append(f"| {row['name']} | {counts} | {diffs} | {delta} | {row['local_duckdb']} | {row['snowflake']} | [evidence]({evidence}) |")
        offset = end
    lines += ['', '[Source, converted SQL and metric implementation code-line links]('
              + base + 'migration/dw-exit/board/README.md#audit-parity-provenance).', '',
              'Approved PowerCenter stable summary ID contract (raw hash Δ retained separately): see [decision]('
              + base + 'migration/dw-exit/audit/README.md#owner-approved-summary-ids).']
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--board', type=Path, default=ROOT / 'migration/dw-exit/board/board.json')
    parser.add_argument('--output', type=Path, default=ROOT / 'migration/dw-exit/audit/PARITY.md')
    args = parser.parse_args()
    branch = subprocess.check_output(['git', 'branch', '--show-current'], cwd=ROOT, text=True).strip() or 'HEAD'
    args.output.write_text(render(args.board.read_text(), branch))
    print('Wrote ' + str(args.output))


if __name__ == '__main__':
    main()
