from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

LOCK = "FIXTURE_SHA.json"


def fingerprints(root: Path) -> dict[str, str]:
    result = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"Corpus symlink refused: {path}")
        if path.is_file() and path != root / LOCK:
            result[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    if not result:
        raise ValueError("Empty corpus")
    return result


def verify_lock(root: Path) -> dict:
    recorded = json.loads((root / LOCK).read_text())
    if recorded.get("files") != fingerprints(root):
        raise ValueError("Corpus hash mismatch; replay refused")
    return recorded


def record_lock(root: Path, reason: str) -> None:
    if not reason.strip():
        raise ValueError("Recording requires an explicit non-empty reason")
    path = root / LOCK
    previous = json.loads(path.read_text()) if path.exists() else {}
    history = previous.get("history", [])
    history.append({"reason": reason, "at": datetime.now(timezone.utc).isoformat(),
                    "previous_files": previous.get("files", {})})
    path.write_text(json.dumps({"version": 1, "files": fingerprints(root), "history": history},
                               indent=2) + "\n")
