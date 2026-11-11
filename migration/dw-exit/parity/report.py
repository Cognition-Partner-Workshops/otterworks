"""Render captured red and green ladder runs without inventing measurements."""
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
    read = lambda path: json.loads(path.read_text())
    text = '# Live billing parity: red to green\n\n'
    text += table(read(args.red), read(args.green))
    text += '\n\n## Supplemental probes — not billing\n\n'
    text += table(read(args.supplemental_red), read(args.supplemental_green))
    text += ('\n\nProfiles cover null counts, min, max and distinct counts. Hash gaps are unmatched '
             'row occurrences, including duplicates; they are not distinct bad business keys. '
             'Every relation also runs sampled value-by-value checks. Raw JSON records SQL and query IDs.\n\n'
             'Finance decision: preserve legacy SET exact-duplicate suppression and expose '
             'suppressed payloads with counts in BILLING_PROBES.SET_DUPLICATE_QUARANTINE. '
             'Billing MULTISET duplicates remain preserved.\n')
    args.output.write_text(text)


if __name__ == '__main__':
    main()
