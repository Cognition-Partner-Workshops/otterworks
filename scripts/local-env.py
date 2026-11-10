"""Generate untracked, per-checkout PostgreSQL credentials for local Compose."""

import os
from pathlib import Path
import secrets


def initialize(path):
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        raise RuntimeError(f"{path} already exists; preserve or update it rather than overwriting credentials") from None
    with os.fdopen(fd, "w") as output:
        for name in ("DB_PASSWORD", "BILLING_SVC_DB_PASSWORD"):
            output.write(f"{name}={secrets.token_hex(32)}\n")


if __name__ == "__main__":
    initialize(Path(__file__).resolve().parents[1] / ".env")
