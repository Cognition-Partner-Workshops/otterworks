"""Fail closed until every non-ETL Teradata reader has stopped."""
import json
from reads import arguments, collect, render


def remaining(data):
    return sum(row['teradata'] for name, row in data.items() if name != 'etl (out of scope)')


if __name__ == '__main__':
    args = arguments(__doc__).parse_args()
    data = collect(args, 'decommission')
    print(json.dumps(data, indent=2) if args.json else render(data))
    for name, row in data.items():
        print(f"{name}: " + (', '.join(f'{a}={n}' for a, n in row['accounts'].items()) or 'no accounts with reads'))
    count = remaining(data)
    print(f'Non-ETL Teradata reads: {count}; ' + ('BLOCKED' if count else 'CLEAR'))
    raise SystemExit(1 if count else 0)
