"""Replay the live legacy API against immutable frozen evidence."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import zlib
from capture import OPERATIONS, fetch

ROOT = Path(__file__).resolve().parent


def field_diff(expected, actual, path="$"):
    if type(expected) is not type(actual):
        return [dict(path=path, change="changed", expected=expected, actual=actual)]
    if isinstance(expected, dict):
        differences = []
        for key in sorted(expected.keys() | actual.keys()):
            child = path + "." + key
            if key not in expected:
                differences.append(dict(path=child, change="added", actual=actual[key]))
            elif key not in actual:
                differences.append(dict(path=child, change="removed", expected=expected[key]))
            else:
                differences.extend(field_diff(expected[key], actual[key], child))
        return differences
    if isinstance(expected, list):
        differences = []
        for index in range(max(len(expected), len(actual))):
            child = f"{path}[{index}]"
            if index >= len(expected):
                differences.append(dict(path=child, change="added", actual=actual[index]))
            elif index >= len(actual):
                differences.append(dict(path=child, change="removed", expected=expected[index]))
            else:
                differences.extend(field_diff(expected[index], actual[index], child))
        return differences
    return [] if expected == actual else [dict(path=path, change="changed", expected=expected, actual=actual)]


def replay(frozen, base):
    manifest = json.loads((frozen / "manifest.json").read_text())
    expected_contracts = {str(contract) for contract in manifest["contracts"]}
    if len(expected_contracts) != len(manifest["contracts"]):
        raise ValueError("Duplicate contracts in frozen manifest")
    baseline = {}
    for op in OPERATIONS:
        for contract in sorted(expected_contracts):
            record = json.loads((frozen / op / f"{contract}.json").read_text())
            if record["operation"] != op or str(record["contract"]) != contract:
                raise ValueError(f"Frozen identity mismatch: {op}/{contract}")
            baseline[op, contract] = record
    report = dict(timestamp=datetime.now(timezone.utc).isoformat(), baseUrl=base,
                  frozen=str(frozen), contractsAdded=[], contractsRemoved=[],
                  operations={op: dict(checked=0, unchanged=0, drifted=0) for op in OPERATIONS},
                  driftedRecords=[], errors=[], complete=False)
    url = base + "/contracts"
    try:
        status, raw = fetch(url)
        listing = json.loads(raw)
        if status != 200 or listing.get("RTN_CD") != "00":
            raise ValueError(f"Contract listing failed: HTTP {status} {listing}")
        contracts = [str(listing[key]) for key in sorted(listing) if key.startswith("CNTR_NO_")]
        if len(contracts) != int(listing["CNTR_CNT"]) or len(set(contracts)) != len(contracts):
            raise ValueError("CNTR_CNT mismatch or duplicate live contracts")
        live_contracts = set(contracts)
        report["contractsAdded"] = sorted(live_contracts - expected_contracts)
        report["contractsRemoved"] = sorted(expected_contracts - live_contracts)
        for op in OPERATIONS:
            for contract in report["contractsRemoved"]:
                report["operations"][op]["checked"] += 1
                report["operations"][op]["drifted"] += 1
                report["driftedRecords"].append(dict(operation=op, contract=contract,
                    differences=[dict(path="$record", change="removed", expected=baseline[op, contract])]))
            for contract in contracts:
                url = f"{base}/{op}/{contract}"
                status, raw = fetch(url)
                actual = dict(status=status, rawSha256=hashlib.sha256(raw).hexdigest())
                try:
                    actual["body"] = json.loads(raw)
                except (ValueError, UnicodeDecodeError) as error:
                    actual["body"] = raw.decode("utf-8", errors="replace")
                    report["errors"].append(dict(url=url, error=f"Invalid JSON: {error}"))
                if contract in expected_contracts:
                    record = baseline[op, contract]
                    expected = {key: record[key] for key in ("status", "rawSha256", "body")}
                    differences = field_diff(expected, actual)
                else:
                    differences = [dict(path="$record", change="added", actual=actual)]
                report["operations"][op]["checked"] += 1
                report["operations"][op]["drifted" if differences else "unchanged"] += 1
                if differences:
                    report["driftedRecords"].append(dict(operation=op, contract=contract, differences=differences))
        report["complete"] = True
    except OSError as error:
        report["errors"].append(dict(url=url, error=str(error)))
        return report, 2
    except (ValueError, KeyError, TypeError) as error:
        report["errors"].append(dict(url=url, error=str(error)))
        return report, 1
    return report, int(bool(report["driftedRecords"] or report["errors"]))


def write_report(report, out):
    out.parent.mkdir(parents=True, exist_ok=True)
    out.with_suffix(".json").write_text(json.dumps(report, indent=2) + "\n")
    lines = ["# Legacy frozen-set drift replay", "", f"Complete: {report['complete']}",
             f"Legacy API: {report['baseUrl']}", "",
             "Contracts added: " + json.dumps(report["contractsAdded"]),
             "Contracts removed: " + json.dumps(report["contractsRemoved"]), "",
             "| Operation | Checked | Unchanged | Drifted |", "| --- | ---: | ---: | ---: |"]
    for op, counts in report["operations"].items():
        lines.append(f"| {op} | {counts['checked']} | {counts['unchanged']} | {counts['drifted']} |")
    for record in report["driftedRecords"]:
        lines += ["", f"## {record['operation']} / {record['contract']}", ""]
        for difference in record["differences"]:
            lines.append("- " + json.dumps(difference, ensure_ascii=False))
    if report["errors"]:
        lines += ["", "## Errors", *["- " + json.dumps(error) for error in report["errors"]]]
    out.with_suffix(".md").write_text("\n".join(lines) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ns", default="iri")
    parser.add_argument("--frozen-dir", type=Path, default=ROOT / "frozen",
                        help="Alternate baseline directory; always read-only")
    parser.add_argument("--out", type=Path, help="Report stem (or .json/.md path), outside frozen")
    args = parser.parse_args()
    frozen = args.frozen_dir.resolve()
    out = args.out or ROOT / "reports" / ("drift-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
    if out.suffix in (".json", ".md"):
        out = out.with_suffix("")
    out = out.resolve()
    for protected in (frozen, (ROOT / "frozen").resolve()):
        if any(path.is_relative_to(protected) for path in (out.with_suffix(".json"), out.with_suffix(".md"))):
            parser.error("--out must be outside frozen directories")
    base = f"http://127.0.0.1:{18080 + zlib.crc32(args.ns.encode()) % 1000}/pinq/v1"
    report, code = replay(frozen, base)
    write_report(report, out)
    total = dict(checked=0, unchanged=0, drifted=0)
    for op, counts in report["operations"].items():
        print(f"{op}: {counts['unchanged']}/{counts['checked']} unchanged, {counts['drifted']} drifted")
        for key in total:
            total[key] += counts[key]
    print(f"Total: {total['unchanged']}/{total['checked']} unchanged, {total['drifted']} drifted")
    print(f"Contracts added: {report['contractsAdded']}; removed: {report['contractsRemoved']}")
    for record in report["driftedRecords"]:
        print(f"Drift {record['operation']}/{record['contract']}: " + json.dumps(record["differences"]))
    for error in report["errors"]:
        print("Error: " + json.dumps(error))
    print(f"Reports: {out}.json / {out}.md")
    print(f"Exit code: {code}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
