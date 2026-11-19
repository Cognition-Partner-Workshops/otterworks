"""Render captured red and green ladder runs without inventing measurements."""

import sys as _run_sys
from pathlib import Path as _RunPath
_run_sys.path.insert(0, str(_RunPath(__file__).resolve().parents[3]))
from warehouse.run_config import render as _run_render

import argparse
import json
from pathlib import Path


def table(before, after):
    old = {row['name']: row for row in before}
    new = {row['name']: row for row in after}
    if not old or old.keys() != new.keys():
        raise ValueError('Both runs must contain the same nonempty relation set')
    lines = ['| Relation | BEFORE rows | Red rows | Green rows | Profile gaps red → green | Hash gaps red → green | Result |',
             '|---|---:|---:|---:|---:|---:|---|']
    for name, red in old.items():
        green = new[name]
        if red['before_count'] != green['before_count']:
            raise ValueError(f'{name}: baseline row count changed')
        status = lambda row: 'GREEN' if row['passed'] else 'RED'
        lines.append(f"| {name} | {red['before_count']:,} | {red['after_count']:,} | {green['after_count']:,} | "
                     f"{red['profile_mismatched_columns']} → {green['profile_mismatched_columns']} | "
                     f"{red['hash_difference']:,} → {green['hash_difference']:,} | {status(red)} → {status(green)} |")
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--red', type=Path, required=True)
    parser.add_argument('--green', type=Path, required=True)
    parser.add_argument('--supplemental-red', type=Path, required=True)
    parser.add_argument('--supplemental-green', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    read = lambda path: json.loads(_run_render(path.read_text()))
    text = '# Live billing parity: red to green\n\n'
    text += table(read(args.red), read(args.green))
    text += '\n\n## Comparison rules\n\n'
    for row in read(args.green):
        padded = row.get('comparison_rules', {}).get('trailing_pad_insensitive', [])
        text += f"- {row['name']}: trailing-pad-insensitive CHAR columns: {', '.join(padded) or 'none'}; all other columns exact.\n"
    text += '\n\n## Supplemental probes — not billing\n\n'
    text += table(read(args.supplemental_red), read(args.supplemental_green))
    text += ('\n\nProfiles cover null counts, min, max and distinct counts. Hash gaps are unmatched '
             'row occurrences, including duplicates; they are not distinct bad business keys. '
             'Every relation also runs sampled value-by-value checks. Raw JSON records SQL and query IDs.\n')
    args.output.write_text(text)


if __name__ == '__main__':
    main()
