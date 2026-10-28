#!/usr/bin/env python3
"""Run the billing_history unit end-to-end without the bundle: ddl.sql then load.sql.

  /home/ubuntu/.venvs/dbx-recon/bin/python dbx/invoicing_history/billing_history/run.py

Thin wrapper: the connection and execution live in _runner.py beside this file so the
SQL being executed stays in sql/ddl.sql and sql/load.sql — inspectable committed
artifacts, not strings built in a program. Idempotent: ddl.sql drops and recreates the
five target tables, load.sql overwrites them from the landed extract. The bundle job
runs the same pair via sql_task; this path is the dev loop / wave-verify rerun.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _runner import main

if __name__ == "__main__":
    raise SystemExit(main())
