"""Initialize namespace schemas or explicitly generate disposable landing fixtures."""

import argparse
from pathlib import Path

from warehouse.seed.generate import generate

from .ingest import business_date
from .session import create_session


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--business-date', required=True)
    parser.add_argument('--landing', type=Path)
    parser.add_argument('--rows', type=int, default=200000)
    parser.add_argument('--seed', type=int, default=1110)
    args = parser.parse_args()
    business_date(args.business_date)
    if args.rows < 0:
        parser.error('rows must be nonnegative')
    if args.landing is not None:
        generate(args.rows, args.seed, args.landing, args.business_date)
    else:
        spark = create_session()
        spark.stop()


if __name__ == '__main__':
    main()
