"""Publish users reports from built Delta tables."""

import argparse
import csv
import os
import tempfile
from contextlib import contextmanager

from .ingest import business_date
from .layout import data_root
from .session import create_session


@contextmanager
def atomic_output(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', newline='',
                                     dir=path.parent, delete=False) as temporary:
        staging = Path(temporary.name)
        try:
            yield temporary
            temporary.close()
            os.replace(staging, path)
        finally:
            staging.unlink(missing_ok=True)


def write_team_counts(path, rows):
    with atomic_output(path) as stream:
        csv.writer(stream, delimiter='|', lineterminator='\n').writerows(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--business-date', required=True)
    args = parser.parse_args()
    business_date(args.business_date)
    spark = create_session()
    try:
        counts = spark.table('gold_users.team_counts').orderBy('team_id')
        write_team_counts(data_root() / 'exports' / args.business_date / 'team_counts.psv',
                          counts.toLocalIterator())
    finally:
        spark.stop()


if __name__ == '__main__':
    main()
