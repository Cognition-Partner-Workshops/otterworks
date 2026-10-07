#!/usr/bin/env python3
"""Mini-scale seed of the Oracle billing estate for the mmp_rt_b3_oracle run.

Wraps the read-only ``oracle_billing_seed`` module: injects a ``mini`` scale
(200 customers / 1,500 invoice lines / 5 core tenants) into ``SCALES`` and runs
``main()`` as ``--ns mmprt --scale mini``. The stock ``demo``/``full`` scales are
too large for an unattended plugin run. Run from the repo root::

    DB_PORT=52521 uv run --with oracledb==2.5.1 python testdata/legacy/mmp_rt_mini_seed.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import oracle_billing_seed  # noqa: E402

MINI_NS = "mmprt"
MINI_SCALE = {"customers": 200, "invoice_lines": 1500, "core_tenants": 5}


def main() -> int:
    oracle_billing_seed.SCALES["mini"] = MINI_SCALE
    sys.argv = [sys.argv[0], "--ns", MINI_NS, "--scale", "mini"]
    return oracle_billing_seed.main()


if __name__ == "__main__":
    sys.exit(main())
