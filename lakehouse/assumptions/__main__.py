import argparse

from lakehouse.coverage.checker import check


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['check'])
    parser.parse_args()
    try:
        raise SystemExit(check(assumptions_only=True))
    except (ValueError, OSError) as exc:
        parser.error(str(exc))


if __name__ == '__main__':
    main()
