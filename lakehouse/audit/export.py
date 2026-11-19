import argparse
import csv
import os
import tempfile
from pathlib import Path

from lakehouse.runtime.ingest import business_date
from lakehouse.runtime.session import create_session


def publish(rows, destination):
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=destination.parent, prefix='.reconciliation-')
    try:
        with os.fdopen(descriptor, 'w', newline='', encoding='utf-8') as handle:
            writer = csv.writer(handle, delimiter='|', lineterminator='\n')
            for row in rows:
                writer.writerow(row)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--business-date', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    business_date(args.business_date)
    spark = create_session()
    try:
        rows = spark.sql(
            "select recon_id, source_count, target_count, difference_count "
            "from gold_audit.m_recon_totals where recon_id <> 21000000001 order by recon_id"
        ).toLocalIterator()
        publish(rows, args.output)
    finally:
        spark.stop()


if __name__ == '__main__':
    main()
