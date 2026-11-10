import argparse
import os
from pathlib import Path

from .harness import licence, setup

parser = argparse.ArgumentParser(description="PowerCenter migration harness")
parser.add_argument("command", choices=["setup", "licence", "before", "parity", "idempotence", "mark", "dbt"])
parser.add_argument("--landing-dir", type=Path)
parser.add_argument('--skip-control', action='store_true')
parser.add_argument('--control-schema')
parser.add_argument('--mapping')
parser.add_argument('--folder')
parser.add_argument('--sample', type=int, default=10)
parser.add_argument('--owner', default='act3-workflow')
parser.add_argument('--amber')
parser.add_argument('--pr-url')
args = parser.parse_args()
if args.control_schema:
    os.environ['PC_CONTROL_SCHEMA'] = args.control_schema
if args.command == "setup":
    setup(args.landing_dir, args.skip_control)
elif args.command == 'licence':
    licence()
elif args.command == 'dbt':
    from .commands import build
    build(args.mapping, args.folder)
else:
    from .commands import dispatch
    if not args.mapping or args.sample < 0:
        parser.error('--mapping required; --sample must be nonnegative')
    dispatch(args)
