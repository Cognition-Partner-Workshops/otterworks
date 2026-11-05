"""Externalized configuration: environment and flags only, never hostnames."""

from dataclasses import dataclass, field
import os
from pathlib import Path

DEFAULT_ROOT = "/tmp/otterworks-legacy"
FILE_GLOB = "CUSTBILL*.dat"
RECORD_WIDTH = 65


def _env_int(name, default):
    raw = os.environ.get(name, "")
    return int(raw) if raw.strip() else default


@dataclass
class Settings:
    root: Path
    strict: bool = False
    spark_master: str = "local[*]"
    archive_retention_days: int = 90
    done_retention_days: int = 30
    delivery_dir: Path | None = None
    distribution: tuple = field(default_factory=tuple)

    @classmethod
    def from_env(cls, root=None, strict=None):
        root = Path(root or os.environ.get("CUSTBILL_ROOT")
                    or os.environ.get("OTTERWORKS_LEGACY_ROOT") or DEFAULT_ROOT)
        strict = (os.environ.get("CUSTBILL_STRICT", "") == "1") if strict is None else strict
        delivery = os.environ.get("CUSTBILL_DELIVERY_DIR", "").strip()
        distribution = tuple(p.strip() for p in os.environ.get("CUSTBILL_DISTRIBUTION", "").split(",")
                             if p.strip())
        return cls(root=root, strict=strict,
                   spark_master=os.environ.get("CUSTBILL_SPARK_MASTER", "local[*]"),
                   archive_retention_days=_env_int("CUSTBILL_ARCHIVE_RETENTION_DAYS", 90),
                   done_retention_days=_env_int("CUSTBILL_DONE_RETENTION_DAYS", 30),
                   delivery_dir=Path(delivery) if delivery else None,
                   distribution=distribution)

    @property
    def drop(self):
        return self.root / "sftp-drop/upload"

    @property
    def incoming(self):
        return self.root / "incoming"

    @property
    def archive(self):
        return self.root / "archive"

    @property
    def parsed(self):
        return self.root / "parsed"

    @property
    def reports(self):
        return self.root / "reports"

    @property
    def control(self):
        # Locks, ledgers and quarantine live outside the stage directories the
        # legacy chain (and the parity harness) treat as outputs.
        return self.root / "control"
