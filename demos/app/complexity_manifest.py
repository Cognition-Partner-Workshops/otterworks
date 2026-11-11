"""Read single-demo v1 and multi-demo v2 complexity registers."""

from __future__ import annotations

import json
from pathlib import Path


def load_demos(path: Path | str) -> dict[str, dict]:
    raw = json.loads(Path(path).read_text())
    version = raw.get("schema_version")
    if type(version) is not int or version not in (1, 2):
        raise ValueError("Unsupported complexity manifest schema_version")
    blocks = [{key: value for key, value in raw.items() if key != "schema_version"}] if version == 1 else raw.get("demos")
    if not isinstance(blocks, list) or not blocks:
        raise ValueError("Complexity manifest requires demo blocks")
    result = {}
    for block in blocks:
        if not isinstance(block, dict) or not isinstance(block.get("demo"), str) or not block["demo"]:
            raise ValueError("Each demo requires a non-empty name")
        if block["demo"] in result:
            raise ValueError("Duplicate complexity demo name")
        if not isinstance(block.get("spec"), str) or not isinstance(block.get("classes"), list):
            raise ValueError("Each demo requires spec and classes")
        ids = [item.get("id") if isinstance(item, dict) else None for item in block["classes"]]
        if any(not isinstance(cid, str) or not cid for cid in ids) or len(set(ids)) != len(ids):
            raise ValueError("Class IDs must be non-empty and unique within a demo")
        result[block["demo"]] = {**block, "schema_version": 1}
    return result


def load_demo(path: Path | str, demo: str) -> dict:
    """Return the selected block in the original v1 reader shape."""
    demos = load_demos(path)
    if demo not in demos:
        raise ValueError(f"Unknown complexity demo: {demo}")
    return demos[demo]
