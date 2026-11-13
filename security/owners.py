from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import yaml

DEFAULT_PATH = Path(__file__).with_suffix(".yaml")


def load(path: Path = DEFAULT_PATH) -> dict[str, dict[str, str]]:
    spec = yaml.safe_load(path.read_text()) or {}
    return spec.get("services") or {}


def missing(services: Iterable[str]) -> list[str]:
    owners = load()
    return sorted(service for service in services if service not in owners)
