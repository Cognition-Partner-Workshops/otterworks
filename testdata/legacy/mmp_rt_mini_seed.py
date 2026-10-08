#!/usr/bin/env python3
"""Mini-scale wrapper around the stock Oracle billing seeder for the
mongo-migration plugin-validation run (namespace ``mmprt``).

Registers a ``mini`` scale on top of ``oracle_billing_seed.SCALES`` without
editing the seeder, then runs its ``main()`` exactly as
``make oracle-billing-seed`` would (``DB_PORT`` defaults to 52521):

    DB_PORT=52521 uv run --with oracledb==2.5.1 testdata/legacy/mmp_rt_mini_seed.py

Writes testdata/legacy/manifests/mmprt.json via the seeder's manifest path.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import oracle_billing_seed

oracle_billing_seed.SCALES["mini"] = {
    "customers": 200,
    "invoice_lines": 1500,
    "core_tenants": 5,
}

if __name__ == "__main__":
    os.environ.setdefault("DB_PORT", "52521")
    sys.argv = [sys.argv[0], "--ns", "mmprt", "--scale", "mini"]
    sys.exit(oracle_billing_seed.main())
