"""Prepare run-scoped Grafana expressions before provisioning."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from warehouse.run_config import RunConfig


def render():
    return Path(__file__).with_name('alerts.yml').read_text().replace('$RUN_TOKEN', RunConfig.from_env().token)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render())
