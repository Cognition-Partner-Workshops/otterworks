#!/usr/bin/env python3
"""Nightly after-tenant parity: rerun the holdout pairs and the JSF replay, report changed verdicts."""

import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.request
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARITY = HERE.parent
sys.path.insert(0, str(PARITY / "mainframe"))
from build_pairs import REPO  # noqa: E402
from decode import decode_records  # noqa: E402

DEFAULT_BASE = "https://t-gf-after.demo.otterworks.app"


def get_json(url, timeout):
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        return error.code, None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        return None, str(error)


def holdout_verdicts(base, timeout, out):
    verdicts = {}
    corpus = subprocess.run(
        [sys.executable, str(PARITY / "mainframe" / "check_pairs.py"), "--candidate",
         f"{sys.executable} {PARITY / 'mainframe' / 'reference' / 'fleben01.py'} --in {{in}} --out {{out}} --period {{period}}"],
        capture_output=True, text=True, cwd=REPO)
    (out / "check_pairs.log").write_text(corpus.stdout + corpus.stderr, encoding="utf-8")
    verdicts["holdout/corpus-and-reference-port"] = {
        "verdict": "agree" if corpus.returncode == 0 else "differ",
        "detail": f"check_pairs.py exit {corpus.returncode}"}
    pairs = json.loads((PARITY / "mainframe" / "pairs.json").read_text(encoding="utf-8"))["pairs"]
    for pair in pairs:
        expected = {}
        for row in decode_records(REPO / pair["expectedOutput"]["BENOUT.dat"]["path"]):
            empid = row["empid"].strip()
            expected[empid] = expected.get(empid, Decimal(0)) + Decimal(row["taxableBenefit"])
        status, body = get_json(f"{base}/api/uk/v1/benefit/periods/{pair['period']}/results", timeout)
        key = f"holdout/{pair['id']}"
        if status != 200 or not isinstance(body, list):
            verdicts[key] = {"verdict": "error", "detail": f"results endpoint returned {status}"}
            continue
        if not body:
            verdicts[key] = {"verdict": "no-after-result",
                             "detail": f"after tenant has no benefit results for {pair['period']}; holdout has {len(expected)} employees"}
            continue
        actual = {}
        for row in body:
            actual[row["employeeNo"]] = actual.get(row["employeeNo"], Decimal(0)) + Decimal(str(row["taxableBenefit"]))
        missing = sorted(set(expected) - set(actual))
        extra = sorted(set(actual) - set(expected))
        unequal = sorted(e for e in set(expected) & set(actual) if expected[e] != actual[e])
        same = not (missing or extra or unequal)
        verdicts[key] = {"verdict": "agree" if same else "differ",
                         "detail": (f"{len(expected)} employees; taxable total holdout {sum(expected.values())} "
                                    f"after {sum(actual.values())}; missing {len(missing)}, extra {len(extra)}, "
                                    f"different {len(unequal)}")}
    return verdicts


def jsf_verdicts(base, timeout, out):
    jsf_out = out / "jsf"
    run = subprocess.run(
        [sys.executable, str(PARITY / "jsf" / "replay.py"), "--base", base, "--stage", "full",
         "--out", str(jsf_out), "--timeout", str(timeout)],
        capture_output=True, text=True, cwd=PARITY / "jsf")
    (out / "replay.log").write_text(run.stdout + run.stderr, encoding="utf-8")
    verdicts = {}
    aborted = next((line for line in (run.stdout + run.stderr).splitlines() if line.startswith("replay failed:")), None)
    corpus = json.loads((PARITY / "jsf" / "requests.json").read_text(encoding="utf-8"))
    results = {}
    for path in sorted(jsf_out.glob("*.json")):
        result = json.loads(path.read_text(encoding="utf-8"))
        for row in result["cases"]:
            results[row["id"]] = row
    cases = corpus["cases"] if isinstance(corpus, dict) else corpus
    for case in cases:
        row = results.get(case["id"])
        key = f"jsf/{case['context']}/{case['id']}"
        if row is None:
            verdicts[key] = {"verdict": "not-run",
                             "detail": f"replay.py exit {run.returncode} before this case" + (f" ({aborted})" if aborted else "")}
        elif row["problems"]:
            verdicts[key] = {"verdict": "differ",
                             "detail": f"HTTP {row['status']}; " + "; ".join(str(p) for p in row["problems"])[:300]}
        else:
            verdicts[key] = {"verdict": "agree", "detail": f"HTTP {row['status']}"}
    return verdicts


def changes(previous, current):
    rows = []
    for key in sorted(set(previous) | set(current)):
        before = previous.get(key, {}).get("verdict", "absent")
        after = current.get(key, {}).get("verdict", "absent")
        if before != after:
            rows.append({"check": key, "was": before, "now": after,
                         "detail": current.get(key, {}).get("detail", "")})
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default=DEFAULT_BASE)
    parser.add_argument("--state", default=str(HERE / "state.json"))
    parser.add_argument("--out", required=True)
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument("--write-state", action="store_true")
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    state_path = Path(args.state)
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.is_file() else {}
    base = args.base.rstrip("/")
    current = {**holdout_verdicts(base, args.timeout, out), **jsf_verdicts(base, args.timeout, out)}
    changed = changes(state.get("verdicts", {}), current)
    counts = {}
    for entry in current.values():
        counts[entry["verdict"]] = counts.get(entry["verdict"], 0) + 1
    report = {"target": base, "previous_commit_state": state.get("recorded_at"),
              "counts": dict(sorted(counts.items())), "changed": changed}
    (out / "changes.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    lines = [f"# After-tenant parity: {len(changed)} changed verdict(s)", "", f"- Target: `{base}`",
             f"- Compared with state recorded at: `{state.get('recorded_at') or 'none (empty state)'}`",
             "- Current counts: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())), ""]
    if changed:
        lines += ["| Check | Was | Now | Detail |", "|---|---|---|---|"]
        lines += [f"| {c['check']} | {c['was']} | {c['now']} | {c['detail'].replace('|', '/')} |" for c in changed]
    else:
        lines.append("No verdict changed.")
    (out / "CHANGES.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    if args.write_state:
        from datetime import datetime, timezone
        new_state = {"target": base, "recorded_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                     "verdicts": dict(sorted(current.items()))}
        state_path.write_text(json.dumps(new_state, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
