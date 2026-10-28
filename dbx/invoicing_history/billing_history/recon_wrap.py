#!/usr/bin/env python3
"""dbx-recon entrypoint with a connector-compat shim for oauth-m2m.

databricks-sql-connector 4.8.0 has no client-credentials path for
`sql.connect(oauth_client_id=..., oauth_client_secret=...)` — it opens the
interactive authorize URL and hangs. This shim keeps the SAME service principal
(env DATABRICKS_CLIENT_ID/SECRET via the SDK) but routes the token mint through
`credentials_provider`, the connector's supported M2M surface — identical to the
harness's own `_databricks_bearer()` (SDK Config().authenticate()) which is used
for its access_token path. Nothing else about the connection or identity changes.

  /home/ubuntu/.venvs/dbx-recon/bin/python recon_wrap.py run --unit billing_history ...
"""
from __future__ import annotations

import sys

import databricks.sql as _dbsql

_orig_connect = _dbsql.connect


def _connect(*args, **kwargs):
    if kwargs.get("oauth_client_id") or kwargs.get("oauth_client_secret"):
        import databricks.sdk.core as sdk_core

        cfg = sdk_core.Config()
        kwargs.pop("oauth_client_id", None)
        kwargs.pop("oauth_client_secret", None)
        kwargs["credentials_provider"] = lambda: cfg.authenticate
    return _orig_connect(*args, **kwargs)


_dbsql.connect = _connect

from recon.cli import main  # noqa: E402

if __name__ == "__main__":
    main()
