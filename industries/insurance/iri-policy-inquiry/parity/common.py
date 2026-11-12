"""Shared I/O for frozen-record parity checks (never mutates the frozen set)."""
import json
from pathlib import Path
import urllib.error
import urllib.request
import zlib
import yaml

ROOT = Path(__file__).resolve().parents[1]
OPERATIONS = ("summary", "values", "funds")


def lineage():
    return yaml.safe_load((ROOT / "lineage/lineage.yaml").read_text())


def records(op):
    paths = sorted((ROOT / "parity/frozen" / op).glob("*.json"))
    if not paths:
        raise ValueError(f"No frozen records for {op}; run parity/capture.py first")
    result = [json.loads(path.read_text()) for path in paths]
    for record in result:
        if record["operation"] != op:
            raise ValueError("Frozen operation mismatch")
    manifest = ROOT / "parity/frozen/manifest.json"
    if manifest.exists():
        expected = json.loads(manifest.read_text())["operations"][op]["responses"]
        if len(result) != expected:
            raise ValueError(f"Incomplete frozen {op}: {len(result)} of {expected}")
    return result


def base_url(ns):
    return f"http://127.0.0.1:{19080 + zlib.crc32(ns.encode()) % 1000}"


def fetch(url):
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        return error.code, json.load(error)


def endpoint(base, op, contract):
    return f"{base}/v1/policies/{contract}/{op}"


def write_report(op, kind, report):
    out = ROOT / "parity/reports"
    out.mkdir(parents=True, exist_ok=True)
    stem = out / f"{op}-{kind}"
    stem.with_suffix(".json").write_text(json.dumps(report, indent=2) + "\n")
    lines = [f"# {op} {kind}", "", f"Summary: `{report['summary']}`", ""]
    for response in report["responses"]:
        lines += [f"## {response['contract']}", "", f"Counts: `{response['counts']}`", ""]
        for item in response.get("fields", []):
            if item["result"] != "pass":
                lines.append("- " + json.dumps(item, ensure_ascii=False))
        for error in response.get("errors", []):
            lines.append("- " + error)
        lines.append("")
    stem.with_suffix(".md").write_text("\n".join(lines) + "\n")
    print(f"{op} {kind}: {report['summary']}")
