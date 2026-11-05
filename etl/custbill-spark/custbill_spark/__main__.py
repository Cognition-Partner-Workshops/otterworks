"""CLI: python -m custbill_spark {ingest|parse|report|chain} [--root DIR] [--strict]."""

import argparse
import logging
import sys

from . import ingest, parse, report
from .config import Settings
from .support import LockBusy, build_session, stage_lock

STAGES = {"ingest": ingest.run, "parse": parse.run, "report": report.run}
EXIT_LOCK_BUSY = 3


def run_chain(settings, spark):
    """Explicit dependencies: each stage starts when the previous one has returned."""
    with stage_lock(settings, "chain"):
        return {name: STAGES[name](settings, spark) for name in ("ingest", "parse", "report")}


def main(argv=None):
    parser = argparse.ArgumentParser(prog="custbill-spark", description=__doc__)
    parser.add_argument("stage", choices=[*STAGES, "chain"])
    parser.add_argument("--root", help="estate root (default: $CUSTBILL_ROOT, $OTTERWORKS_LEGACY_ROOT)")
    parser.add_argument("--strict", action="store_true",
                        help="quarantine files with invalid records or trailer mismatches")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args(argv)
    logging.basicConfig(level=args.log_level.upper(),
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s", stream=sys.stderr)
    settings = Settings.from_env(root=args.root, strict=args.strict or None)
    spark = build_session(settings, f"custbill-{args.stage}")
    try:
        if args.stage == "chain":
            run_chain(settings, spark)
        else:
            STAGES[args.stage](settings, spark)
    except LockBusy as exc:
        logging.getLogger("custbill_spark").error("%s", exc)
        return EXIT_LOCK_BUSY
    except Exception:
        logging.getLogger("custbill_spark").exception("%s failed", args.stage)
        return 1
    finally:
        spark.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
