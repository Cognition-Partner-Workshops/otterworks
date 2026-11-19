import argparse
import os
import subprocess
from pathlib import Path

import yaml

from lakehouse.runtime.layout import data_root

from .graph import PIPELINE, business_date, load
from .runner import execute, namespace_lock, run


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['check', 'run', 'execute'])
    parser.add_argument('--pipeline', type=Path, default=PIPELINE)
    parser.add_argument('--dag', default='lakehouse_daily')
    parser.add_argument('--node')
    parser.add_argument('--business-date')
    parser.add_argument('--landing', type=Path)
    args = parser.parse_args()
    try:
        dags = load(args.pipeline)
        if args.command == 'check':
            print(f'Pipeline: {len(dags)} DAGs, {sum(len(dag["nodes"]) for dag in dags.values())} tasks, valid')
            return 0
        business_date(args.business_date)
        landing = args.landing or Path(os.environ.get('SFX_LH_LANDING', data_root() / 'landing'))
        dag = dags[args.dag]
        if args.command == 'run':
            return run(dag, landing, args.business_date)
        node = next(node for node in dag['nodes'] if node['id'] == args.node)
        with namespace_lock():
            execute(node, landing, args.business_date)
        return 0
    except (ValueError, OSError, RuntimeError, KeyError, StopIteration, subprocess.CalledProcessError, yaml.YAMLError) as exc:
        parser.error(str(exc))


if __name__ == '__main__':
    raise SystemExit(main())
