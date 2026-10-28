"""Run dbx-recon via the harness's supported SDK-credentials path.

The 0.6.1 harness connects with `credentials_provider=Config().authenticate`,
but with this connector/SDK combo `Config().authenticate()` returns a headers
dict and the connector invokes `credentials_provider()` expecting a *header
factory* callable -> 'dict' object is not callable. Session-local shim (same
as wave-1's documented session patches): wrap authenticate so the provider
returns the factory the connector expects. Same service-principal identity
(d9d1c4ec-...), same auth path the harness chose - not a guard workaround.

Runs `python -m recon.cli` with the plugin-cache harness on sys.path;
invoke from the repo root so .migration/allowed_targets.json resolves.
"""
import os, runpy, sys
from databricks.sdk.core import Config
import databricks.sql as dbsql

HARNESS = "/opt/.devin/plugins/cache/github.com_Cognition-Partner-Workshops_dbx-migration-plugin-5890f19a/0.6.1/skills/data-reconciliation/harness"

sys.path.insert(0, HARNESS)
import recon.adapters as adapters


def _connect(http_path=None):
    host = os.environ["DATABRICKS_HOST"].removeprefix("https://").removeprefix("http://").rstrip("/")
    http_path = http_path or os.environ["DATABRICKS_HTTP_PATH"]
    if os.environ.get("DATABRICKS_AUTH_TYPE") == "env-oidc" and not os.environ.get("DATABRICKS_OIDC_TOKEN"):
        import subprocess
        audience = os.environ.get("DATABRICKS_DEVIN_AUDIENCE", "databricks")
        os.environ["DATABRICKS_OIDC_TOKEN"] = subprocess.run(
            ["devin-oidc", "token", "--audience", audience],
            check=True, capture_output=True, text=True).stdout.strip()
    cfg = Config()
    # connector calls provider() -> header_factory; header_factory() -> headers dict
    return dbsql.connect(server_hostname=host, http_path=http_path,
                         credentials_provider=lambda: cfg.authenticate)


adapters._databricks_connect = _connect

sys.exit_code = runpy.run_module("recon.cli", run_name="__main__")
