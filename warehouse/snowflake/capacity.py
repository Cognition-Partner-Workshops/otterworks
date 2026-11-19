"""Render workload capacity SQL without opening a Snowflake connection."""
import argparse
from pathlib import Path
import sys

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from warehouse.run_config import RunConfig

WORKLOADS = tuple(yaml.safe_load(Path(__file__).with_name('workloads.yml').read_text()))


def render(config=None):
    config = config or RunConfig.from_env()
    monitor = config.database + '_CREDITS'
    statements = [f'CREATE RESOURCE MONITOR IF NOT EXISTS {monitor};',
                  f'ALTER RESOURCE MONITOR {monitor} SET CREDIT_QUOTA = 25 '
                  'FREQUENCY = MONTHLY START_TIMESTAMP = IMMEDIATELY '
                  'TRIGGERS ON 80 PERCENT DO NOTIFY ON 100 PERCENT DO SUSPEND_IMMEDIATE;']
    for workload in WORKLOADS:
        name = config.database + '_' + workload.upper() + '_WH'
        statements.extend([f'CREATE WAREHOUSE IF NOT EXISTS {name} INITIALLY_SUSPENDED = TRUE;',
                           f'ALTER WAREHOUSE {name} SET WAREHOUSE_SIZE = XSMALL '
                           f'AUTO_SUSPEND = 60 AUTO_RESUME = TRUE RESOURCE_MONITOR = {monitor};'])
    return '\n'.join(statements) + '\n'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    print(render(), end='')
