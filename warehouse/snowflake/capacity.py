"""Render workload capacity SQL without opening a Snowflake connection."""
import argparse
import re
from pathlib import Path
import sys

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from warehouse.run_config import RunConfig

# Snowflake bills a running warehouse per second with a 60-second minimum per resume.
CREDITS_PER_HOUR = {'XSMALL': 1, 'SMALL': 2, 'MEDIUM': 4, 'LARGE': 8}
MINIMUM_SECONDS = 60
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


def sizing(config=None):
    """Size and auto-suspend per workload warehouse, read back from the rendered capacity SQL."""
    found = re.findall(r'ALTER WAREHOUSE (\w+) SET WAREHOUSE_SIZE = (\w+) AUTO_SUSPEND = (\d+)', render(config))
    return {workload: {'warehouse': name, 'size': size, 'auto_suspend_seconds': int(suspend)}
            for workload, (name, size, suspend) in zip(WORKLOADS, found)}


def estimate(timings, runs_per_month=30, config=None):
    """Credits for one daily run per workload: max(runtime, 60 s minimum) plus the idle auto-suspend tail."""
    seconds = {workload: 0.0 for workload in WORKLOADS}
    for timing in timings:
        seconds[timing['workload']] += timing['seconds']
    rows = []
    for workload, warehouse in sizing(config).items():
        used = seconds[workload]
        billed = max(used, MINIMUM_SECONDS) + warehouse['auto_suspend_seconds'] if used else 0.0
        credits = billed / 3600 * CREDITS_PER_HOUR[warehouse['size']]
        rows.append({'workload': workload, **warehouse, 'duckdb_seconds': round(used, 3),
                     'billed_seconds': round(billed, 3), 'credits_per_run': round(credits, 6),
                     'credits_per_month': round(credits * runs_per_month, 4)})
    return {'basis': 'DuckDB local wall-clock runtimes; one resume per workload per daily run', 'runs_per_month': runs_per_month,
            'workloads': rows, 'credits_per_run': round(sum(r['credits_per_run'] for r in rows), 6),
            'credits_per_month': round(sum(r['credits_per_month'] for r in rows), 4)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    print(render(), end='')
