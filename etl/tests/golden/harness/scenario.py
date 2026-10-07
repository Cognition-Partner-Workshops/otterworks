"""Scenario files: etl/tests/golden/<script>/<scenario>/scenario.json.

Schema (every key except frozen_time is optional):

    {
      "description": "what this scenario pins down",
      "frozen_time": "2026-03-15T02:00:00Z",     # wall clock inside the script
      "config_overrides": {"section": {"key": "value" | null} | null},
      "seed": {
        "sqs":      {"<queue>": [<json value> | "<raw string body>", ...]},
        "dynamodb": {"<table>": [{<plain JSON item; numbers become Decimal>}]},
        "s3":       [{"bucket", "key", "body", "format": "json"|"jsonl"|"text",
                      "gzip": false, "content_type": null, "storage_class": null}],
        "postgres": {"<table>": [{<column>: <value>}]},
        "http":     {"documents": [...], "files": [...],
                     "errors": {"documents"|"files": {"<page>": <http status>}}}
      }
    }
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from . import settings

SEED_KEYS = {"sqs", "dynamodb", "s3", "postgres", "http"}


@dataclass(frozen=True)
class Scenario:
    script: str
    name: str
    path: Path
    description: str
    frozen_time: str
    seed: dict = field(default_factory=dict)
    config_overrides: dict = field(default_factory=dict)

    @property
    def golden_dir(self) -> Path:
        return self.path / "golden"

    @property
    def label(self) -> str:
        return "%s/%s" % (self.script, self.name)


def load(path: Path) -> Scenario:
    data = json.loads((path / "scenario.json").read_text())
    unknown = set(data.get("seed", {})) - SEED_KEYS
    if unknown:
        raise ValueError("%s: unknown seed keys %s" % (path, sorted(unknown)))
    if "frozen_time" not in data:
        raise ValueError("%s: frozen_time is required" % path)
    return Scenario(
        script=path.parent.name,
        name=path.name,
        path=path,
        description=data.get("description", ""),
        frozen_time=data["frozen_time"],
        seed=data.get("seed", {}),
        config_overrides=data.get("config_overrides", {}),
    )


def discover(script: str, name: str | None = None) -> list[Scenario]:
    scripts = settings.SCRIPTS if script == "all" else (script,)
    found = []
    for script_name in scripts:
        if script_name not in settings.SCRIPTS:
            raise ValueError(
                "unknown script %r (expected one of %s or 'all')"
                % (script_name, ", ".join(settings.SCRIPTS))
            )
        root = settings.GOLDEN_DIR / script_name
        if not root.is_dir():
            continue
        for path in sorted(
            p for p in root.iterdir() if (p / "scenario.json").is_file()
        ):
            if name is None or path.name == name:
                found.append(load(path))
    return found
