"""Local operational events, without credentials or source row contents."""
from datetime import datetime, timezone
from functools import wraps
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
EVENTS = {"load_started", "load_success", "load_failure", "row_count_drop", "null_spike"}


def emit(event, **values):
    if event not in EVENTS:
        raise ValueError("Unknown operational event")
    path = Path(os.getenv("SFX_LOG_PATH", str(ROOT / "migration/dw-exit/.runs/logs/pipeline.jsonl")))
    body = {"timestamp": datetime.now(timezone.utc).isoformat(), "event": event,
            "run": os.getenv("RUN_TOKEN", "sfx1119"), **values}
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a") as stream:
            stream.write(json.dumps(body, default=str) + "\n")
    except OSError:
        print("Unable to write operational event", file=sys.stderr)


def operation(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        emit("load_started")
        try:
            result = function(*args, **kwargs)
        except Exception as error:
            emit("load_failure", error_type=type(error).__name__)
            raise
        emit("load_success")
        return result
    return wrapped


def record_checks(result):
    for name, check in result["checks"].items():
        if check["firing"]:
            emit(name, value=check["value"], threshold=check["threshold"])
    return result
