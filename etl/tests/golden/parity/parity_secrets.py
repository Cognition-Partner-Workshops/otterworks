"""Secrets backend for the parity Airflow container: records every Variable a DAG reads.

Configured as AIRFLOW__SECRETS__BACKEND (harness/airflow_container.py), so Airflow asks it
first on each Variable.get / {{ var.value.x }}. It answers from the same AIRFLOW_VAR_* env the
environment-variables backend would use, and prints one marker line per read to the process
stdout, which `airflow dags test` (tasks run in-process) hands back to the parity runner. The
runner checks each per-scenario override against what the DAG actually read.
"""

from __future__ import annotations

import json
import os
import sys

from airflow.secrets import BaseSecretsBackend

MARKER = "PARITY_VARIABLE_READ "


class ParityVariableLog(BaseSecretsBackend):
    def get_conn_value(self, conn_id: str) -> str | None:
        return None

    def get_variable(self, key: str) -> str | None:
        value = os.environ.get("AIRFLOW_VAR_%s" % key.upper())
        sys.__stdout__.write(
            "%s%s\n" % (MARKER, json.dumps({"key": key, "value": value}))
        )
        sys.__stdout__.flush()
        return value
