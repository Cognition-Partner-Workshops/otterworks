"""Run the estate Make target with an encrypted, ephemeral JWT key file."""

import sys as _run_sys
from pathlib import Path as _RunPath
_run_sys.path.insert(0, str(_RunPath(__file__).resolve().parents[3]))
from warehouse.run_config import render as _run_render

import os
import secrets
import subprocess

from cryptography.hazmat.primitives import serialization


def main():
    key = serialization.load_pem_private_key(os.environ['SNOWFLAKE_PRIVATE_KEY'].encode(), password=None)
    passphrase = secrets.token_urlsafe(48)
    environment = dict(os.environ)
    environment['PRIVATE_KEY_PASSPHRASE'] = passphrase
    environment[_run_render('SNOWFLAKE_CONNECTIONS___RUN_DATABASE___PRIVATE_KEY_PASSPHRASE')] = passphrase
    environment['SNOWFLAKE_QUERY_TAG'] = _run_render('{"run":"__RUN_TOKEN__","act":"prove","step":"snowconvert"}')
    environment['SNOWFLAKE_PRIVATE_KEY'] = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.BestAvailableEncryption(passphrase.encode())).decode()
    return subprocess.call(['make', 'sfx-teradata-snowconvert', _run_render('NS=__BEFORE_NAMESPACE__')], env=environment)


if __name__ == '__main__':
    raise SystemExit(main())
