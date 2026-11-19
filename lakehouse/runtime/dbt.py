import argparse
import os

from dbt.cli.main import dbtRunner

from .ingest import business_date
from .layout import ROOT, data_root
from .session import create_session


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--select', help='dbt selection expression, e.g. tag:billing')
    args = parser.parse_args()
    business_date(os.environ['BUSINESS_DATE'])
    root = data_root()
    os.environ['LAKEHOUSE_DELTA_ROOT'] = str(root / 'delta')
    spark = create_session()
    try:
        arguments = ['build', '--indirect-selection', 'buildable',
                     '--project-dir', str(ROOT / 'dbt'), '--profiles-dir', str(ROOT / 'dbt')]
        if args.select:
            arguments += ['--select', args.select]
        result = dbtRunner().invoke(arguments)
        if not result.success:
            raise SystemExit(1)
    finally:
        spark.stop()


if __name__ == '__main__':
    main()
