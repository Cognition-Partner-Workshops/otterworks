import argparse

from .checker import check


def main():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest='command', required=True)
    command = commands.add_parser('check')
    command.add_argument('--strict', action='store_true')
    args = parser.parse_args()
    try:
        raise SystemExit(check(strict=args.strict))
    except (ValueError, OSError) as exc:
        parser.error(str(exc))


if __name__ == '__main__':
    main()
