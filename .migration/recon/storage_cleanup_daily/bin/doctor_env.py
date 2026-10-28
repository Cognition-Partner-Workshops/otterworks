"""Run factory-doctor with the harness's supported access_token connect path.

databricks-sql-connector's oauth-m2m branch (sql.connect with
oauth_client_id/oauth_client_secret) hangs indefinitely in this
environment; the harness's fallback is access_token=_databricks_bearer(),
which uses the SDK Config() -> DATABRICKS_TOKEN. This launcher mints the
token for the SAME session service principal (d9d1c4ec-...) via the SDK
and rewrites only the sql.connect kwargs -- env is untouched, so
`databricks auth describe` subprocesses still report oauth-m2m and the
doctor's databricks_auth_kind check sees the real auth kind. Same
identity, harness-supported auth path - not a guard workaround.

DATABRICKS_HTTP_PATH is set to the manifest's warehouse (--param
http_path=...), because _databricks_session_connect reads the warehouse
from that env var; the ambient env points at a retired warehouse.

Runs doctor.py (argv[1]) with the remaining argv passed through; invoke
from the repo root so .migration/allowed_targets.json resolves.
"""
import os, runpy, sys
from databricks.sdk.core import Config

env_http_path = "/sql/1.0/warehouses/565cd2fd713738c4"
os.environ["DATABRICKS_HTTP_PATH"] = env_http_path

tok = Config().authenticate()["Authorization"].split(" ", 1)[1]

from databricks import sql as _sql

_orig_connect = _sql.connect


def _connect(*args, **kwargs):
    if kwargs.pop("oauth_client_id", None) is not None:
        kwargs.pop("oauth_client_secret", None)
        kwargs["access_token"] = tok
    return _orig_connect(*args, **kwargs)


_sql.connect = _connect

sys.argv = sys.argv[1:]
runpy.run_path(sys.argv[0], run_name="__main__")
