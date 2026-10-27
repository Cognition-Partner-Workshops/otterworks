#!/usr/bin/env python3
"""Nightly after-tenant parity: rerun the holdout pairs and the JSF cases (as read-only REST calls), report changed verdicts."""

import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
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
        try:
            return error.code, json.loads(error.read().decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
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


def resolve(value, path):
    for part in [p for p in path.split(".") if p]:
        if isinstance(value, list):
            index = int(part)
            value = value[index] if index < len(value) else _MISSING
        elif isinstance(value, dict):
            value = value.get(part, _MISSING)
        else:
            value = _MISSING
        if value is _MISSING:
            break
    return value


_MISSING = object()


def same(expected, actual):
    if isinstance(expected, bool) or isinstance(actual, bool) or expected is None or actual is None:
        return expected == actual
    try:
        return Decimal(str(expected)) == Decimal(str(actual))
    except ArithmeticError:
        return expected == actual


def check(body, rule):
    actual = resolve(body, rule["path"])
    label = rule["path"] or "body"
    if actual is _MISSING:
        return f"{label} missing"
    if "equals" in rule:
        return None if same(rule["equals"], actual) else f"{label}: expected {rule['equals']!r}, got {actual!r}"
    if "length" in rule:
        size = len(actual) if isinstance(actual, (list, dict, str)) else None
        return None if size == rule["length"] else f"{label}: expected {rule['length']} entries, got {size}"
    if "contains_text" in rule:
        return None if isinstance(actual, str) and rule["contains_text"] in actual else f"{label}: no {rule['contains_text']!r}"
    if "contains_item" in rule:
        wanted = rule["contains_item"]
        found = isinstance(actual, list) and any(
            isinstance(entry, dict) and all(same(v, entry.get(k, _MISSING)) if k in entry else False for k, v in wanted.items())
            for entry in actual)
        return None if found else f"{label}: no entry matching {wanted}"
    raise ValueError(f"unknown check {rule}")


def substitute(text, today):
    previous = (today.replace(day=1) - timedelta(days=1)).strftime("%Y%m")
    return text.replace("{today}", today.isoformat()).replace("{previous_month}", previous)


def jsf_verdicts(base, timeout, out):
    spec = json.loads((HERE / "rest_cases.json").read_text(encoding="utf-8"))
    corpus = json.loads((PARITY / "jsf" / "requests.json").read_text(encoding="utf-8"))["cases"]
    if [case["id"] for case in corpus] != [case["id"] for case in spec["cases"]]:
        raise SystemExit("rest_cases.json does not cover the JSF corpus case for case")
    today = datetime.now(timezone.utc).date()
    verdicts, evidence = {}, []
    for case in spec["cases"]:
        key = f"jsf/{case['context']}/{case['id']}"
        if "not_run" in case:
            verdicts[key] = {"verdict": "not-run", "detail": case["not_run"]}
            continue
        problems, calls = [], []
        for request in case["requests"]:
            url = base + spec["api_prefix"] + substitute(request["path"], today)
            status, body = get_json(url, timeout)
            calls.append({"url": url, "status": status, "body": body})
            if status != request["status"]:
                problems.append(f"GET {request['path']}: HTTP {status}, expected {request['status']}"
                                + (f" ({body.get('code')})" if isinstance(body, dict) and body.get("code") else ""))
                continue
            for rule in request["expect"]:
                rule = {**rule, **({"equals": substitute(rule["equals"], today)} if isinstance(rule.get("equals"), str) else {})}
                problem = check(body, rule)
                if problem:
                    problems.append(f"GET {request['path']}: {problem}")
        evidence.append({"id": case["id"], "jsf_fact": case["jsf_fact"], "problems": problems, "calls": calls})
        verdicts[key] = {"verdict": "differ" if problems else "agree",
                         "detail": "; ".join(problems)[:400] if problems else "REST answer matches the JSF fact"}
    (out / "rest_replay.json").write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
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
        new_state = {"target": base, "recorded_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                     "verdicts": dict(sorted(current.items()))}
        state_path.write_text(json.dumps(new_state, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
