"""Run dbx-recon with the session service principal's minted access_token.

The 0.6.1 harness passes the SDK's `Config().authenticate` (a header
factory `() -> dict`) directly as `credentials_provider`, but
databricks-sql-connector 4.8's ExternalAuthProvider calls
`credentials_provider()` expecting it to RETURN the header factory, so the
connect fails with `'dict' object is not callable`. The oauth-m2m kwargs
branch hangs indefinitely in this environment. This launcher patches
`recon.adapters._databricks_connect` to mint a token for the SAME session
service principal (d9d1c4ec-...) via the SDK and pass it as access_token.
Same identity, same env -- not a guard workaround.

Runs `python -m recon.cli` with the plugin-cache harness on sys.path;
invoke from the repo root so .migration/allowed_targets.json resolves.
"""
import os, runpy, sys
from databricks.sdk.core import Config

HARNESS = "/opt/.devin/plugins/cache/github.com_Cognition-Partner-Workshops_dbx-migration-plugin-5890f19a/0.6.1/skills/data-reconciliation/harness"
sys.path.insert(0, HARNESS)

import recon.adapters as adapters
from databricks import sql as _sql


def _connect(http_path=None):
    host = os.environ["DATABRICKS_HOST"].removeprefix("https://").removeprefix("http://").rstrip("/")
    hp = http_path or os.environ["DATABRICKS_HTTP_PATH"]
    tok = Config().authenticate()["Authorization"].split(" ", 1)[1]
    return _sql.connect(server_hostname=host, http_path=hp, access_token=tok)


adapters._databricks_connect = _connect

sys.argv = ["dbx-recon"] + sys.argv[1:]
runpy.run_module("recon.cli", run_name="__main__")
