import os

from dbt.cli.main import dbtRunner

from .ingest import business_date
from .layout import ROOT, data_root
from .session import create_session


def main():
    business_date(os.environ['BUSINESS_DATE'])
    root = data_root()
    os.environ['LAKEHOUSE_DELTA_ROOT'] = str(root / 'delta')
    spark = create_session()
    try:
        result = dbtRunner().invoke(['build', '--project-dir', str(ROOT / 'dbt'),
                                     '--profiles-dir', str(ROOT / 'dbt')])
        if not result.success:
            raise SystemExit(1)
    finally:
        spark.stop()


if __name__ == '__main__':
    main()
