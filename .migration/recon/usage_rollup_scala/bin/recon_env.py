"""Run dbx-recon via the harness's supported access_token path.

oauth-m2m (DATABRICKS_CLIENT_ID/SECRET -> sql.connect) hangs in this
environment; the harness's fallback is access_token=_databricks_bearer(),
which uses the SDK Config() -> DATABRICKS_TOKEN. This launcher mints the
token for the SAME session service principal (d9d1c4ec-...) via the SDK
and drops the client vars so _databricks_connect takes the token branch.
Same identity, harness-supported auth path - not a guard workaround.

Runs `python -m recon.cli` with the plugin-cache harness on sys.path;
invoke from the repo root so .migration/allowed_targets.json resolves.
"""
import os, sys, subprocess
from databricks.sdk.core import Config

HARNESS = "/opt/.devin/plugins/cache/github.com_Cognition-Partner-Workshops_dbx-migration-plugin-5890f19a/0.6.1/skills/data-reconciliation/harness"

tok = Config().authenticate()["Authorization"].split(" ", 1)[1]
env = dict(os.environ)
env["DATABRICKS_TOKEN"] = tok
env.pop("DATABRICKS_CLIENT_ID", None)
env.pop("DATABRICKS_CLIENT_SECRET", None)
env.pop("DATABRICKS_AUTH_TYPE", None)
env["PYTHONPATH"] = HARNESS + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
sys.exit(subprocess.call([sys.executable, "-m", "recon.cli"] + sys.argv[1:], env=env))
