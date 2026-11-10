import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
PROFILES = {"small": "1g", "large": "2g"}


def arguments(job):
    if not re.fullmatch(r"[a-z][a-z0-9_]*", job):
        raise ValueError("Invalid job identifier")
    entry = json.loads((ROOT / "jobs/registry" / f"{job}.yaml").read_text())
    if entry["status"] == "snowflake":
        raise ValueError("Snowflake jobs cannot be submitted to Spark")
    args = ["/opt/spark/bin/spark-submit", "--master", "spark://spark-master:7077",
            "--deploy-mode", "client", "--properties-file", str(ROOT / "template/spark-defaults.conf"),
            "--executor-memory", PROFILES[entry["profile"]]]
    if entry["language"] == "python":
        args += ["--py-files", str(ROOT / ".cache/common.zip"), str(ROOT / "jobs/py" / f"{job}.py")]
    elif entry["language"] == "scala":
        args += ["--class", entry["class"], str(ROOT / ".cache/sfx-spark-jobs.jar")]
    else:
        raise ValueError("Unsupported language")
    return args


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Usage: submit.sh <job>")
    command = arguments(sys.argv[1])
    os.execv(command[0], command)
