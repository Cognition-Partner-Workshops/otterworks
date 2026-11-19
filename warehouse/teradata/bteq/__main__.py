
import sys as _run_sys
from pathlib import Path as _RunPath
_run_sys.path.insert(0, str(_RunPath(__file__).resolve().parents[3]))
from warehouse.run_config import render as _run_render

import argparse
import sys
from pathlib import Path
from .runner import Runner


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', nargs='?', choices=['run'])
    parser.add_argument('file', nargs='?')
    parser.add_argument('--var', action='append', default=[])
    args = parser.parse_args()
    with Runner(variables=dict(v.split('=', 1) for v in args.var)) as runner:
        return runner.run(_run_render(Path(args.file).read_text()) if args.file else _run_render(sys.stdin.read()))


if __name__ == '__main__':
    sys.exit(main())
