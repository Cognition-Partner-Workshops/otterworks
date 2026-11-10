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
        return runner.run(Path(args.file).read_text() if args.file else sys.stdin.read())


if __name__ == '__main__':
    sys.exit(main())
