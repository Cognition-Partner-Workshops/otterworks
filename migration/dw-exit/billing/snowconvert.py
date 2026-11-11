"""Run the estate Make target with an encrypted, ephemeral JWT key file."""
import os
import secrets
import subprocess

from cryptography.hazmat.primitives import serialization


def main():
    key = serialization.load_pem_private_key(os.environ['SNOWFLAKE_PRIVATE_KEY'].encode(), password=None)
    passphrase = secrets.token_urlsafe(48)
    environment = dict(os.environ)
    environment['PRIVATE_KEY_PASSPHRASE'] = passphrase
    environment['SNOWFLAKE_CONNECTIONS_SFX_D1110_PRIVATE_KEY_PASSPHRASE'] = passphrase
    environment['SNOWFLAKE_QUERY_TAG'] = '{"run":"sfx-d1110","act":"prove","step":"snowconvert"}'
    environment['SNOWFLAKE_PRIVATE_KEY'] = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.BestAvailableEncryption(passphrase.encode())).decode()
    return subprocess.call(['make', 'sfx-teradata-snowconvert', 'NS=sfx-d1110-before'], env=environment)


if __name__ == '__main__':
    raise SystemExit(main())
