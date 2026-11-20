"""Run the billing Spark jobs locally on the fixture landing files and write their lake outputs.

The legacy JDBC tables are the landing files loaded verbatim (etl/spark/fixture/load_tdemu.sh),
so jdbc_read is served from landing with PostgreSQL's lower-case column names. Writes stay in the lake.
"""
import argparse
import os
from pathlib import Path
import runpy
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
JOBS = ROOT / 'etl/spark/jobs/py'
sys.path.insert(0, str(JOBS))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--landing', type=Path, default=ROOT / 'migration/dw-exit/.runs/spark/landing')
    parser.add_argument('--lake', type=Path, default=ROOT / 'migration/dw-exit/.runs/spark/lake')
    parser.add_argument('--rows', type=int, default=200)
    args = parser.parse_args()
    if not (args.landing / 'billing').is_dir():
        subprocess.run([sys.executable, str(ROOT / 'etl/spark/fixture/generate_fixture.py'), '--rows', str(args.rows),
                        '--output', str(args.landing)], check=True)
    os.environ.update(LANDING_DIR=str(args.landing.resolve()), LAKE_DIR=str(args.lake.resolve()))
    from common import runtime

    def jdbc_read(spark, table):
        frame = runtime.landing(spark, table.split('.')[1].upper())
        return frame.toDF(*[column.lower() for column in frame.columns])

    save = runtime.save
    runtime.jdbc_read = jdbc_read
    runtime.save = lambda frame, area, name, jdbc_table=None, mode='overwrite': save(frame, area, name)
    for job in sorted(JOBS.glob('billing_*.py')):
        runpy.run_path(str(job), run_name='__main__')
        print(job.stem, flush=True)


if __name__ == '__main__':
    main()
