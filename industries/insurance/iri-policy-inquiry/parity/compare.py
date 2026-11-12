"""Compare IRI responses to frozen legacy values using only lineage-defined transforms."""
import argparse
from collections import Counter
from datetime import datetime
from decimal import Decimal
import os
import re
from common import OPERATIONS, base_url, endpoint, fetch, lineage, records, write_report


def transform(value, rule, data, row, start=0, limit=50):
    kind = rule["kind"]
    if kind == "identity":
        return value
    if kind == "date":
        if not re.fullmatch(r"\d{8}", value):
            raise ValueError(f"Invalid YYYYMMDD: {value}")
        return datetime.strptime(value, "%Y%m%d").date().isoformat()
    if kind in ("decimal", "integer", "page-count"):
        if not re.fullmatch(r"\d+", str(value)):
            raise ValueError(f"Invalid unsigned digits: {value}")
        number = int(value)
        if kind == "decimal":
            return Decimal(number).scaleb(-rule["scale"])
        if kind == "page-count":
            return max(0, min(limit, number - start))
        return number
    if kind == "enum":
        return rule["values"][value]
    if kind == "status":
        return data["status_codes"][value]
    if kind == "page-start":
        return start
    if kind == "config":
        return os.environ[row["config"]]
    raise ValueError(f"No scalar transform for {kind}")


def read_path(body, path):
    current = body
    for name, index in re.findall(r"([^.\[\]]+)(?:\[(\d+)\])?", path):
        current = current[name]
        if index:
            current = current[int(index)]
    return current


def evaluate(record, data, actual=None, actual_status=None, dry=False, start=0, limit=50):
    body = record["body"]
    fields = []
    op = record["operation"]
    rows = [r for r in data["rows"] if r["operation"] == op]
    known = {r["legacy"] for r in rows}
    for key in body:
        normalized = re.sub(r"_\d{2}$", "_NN", key)
        if key not in known and normalized not in known:
            fields.append(dict(field=key, result="fail", error="Legacy field missing from lineage"))
    if op == "funds" and body.get("RTN_CD") == "00":
        count = int(body["FUND_CNT"])
        for key in body:
            if re.search(r"_\d{2}$", key) and not 1 <= int(key[-2:]) <= count:
                fields.append(dict(field=key, result="fail", error="Suffix outside FUND_CNT"))
    for row in rows:
        legacy, path = row["legacy"], row["iri"]
        condition = row.get("when")
        if condition and body.get(legacy) != condition["equals"]:
            continue
        conditional_signoff = any(r["status"] == "sign-off" and r.get("when", {}).get("equals") == body.get(legacy)
                                 and r["legacy"] == legacy for r in rows if r.get("when"))
        if row["status"] in ("sign-off", "not-in-operation", "omitted-optional"):
            # Still parse sourced sign-off values in dry-run, without declaring parity.
            error = None
            transformed = []
            keys = sorted(k for k in body if re.fullmatch(re.escape(legacy).replace("_NN", r"_\d{2}"), k))
            if body.get("RTN_CD") == "00":
                for key in keys:
                    try:
                        value = transform(body[key], data["rules"][row["rule"]], data, row, start, limit)
                        transformed.append(dict(field=key, value=str(value)))
                    except (ValueError, KeyError, TypeError) as exc:
                        # Unknown enums explicitly on sign-off are not invented.
                        if row["rule"] != "policy-status":
                            error = str(exc)
            fields.append(dict(field=legacy, iri=path, result="fail" if error else row["status"],
                               note=row["note"], transformed=transformed, **({"error": error} if error else {})))
            continue
        if conditional_signoff:
            continue
        if body.get("RTN_CD") != "00" and legacy != "RTN_CD":
            continue
        kind = data["rules"][row["rule"]]["kind"]
        if kind == "container":
            if not dry:
                try:
                    if not isinstance(read_path(actual, path), dict):
                        raise ValueError("Expected object")
                    fields.append(dict(field=legacy, iri=path, result="pass"))
                except (KeyError, IndexError, TypeError, ValueError) as exc:
                    fields.append(dict(field=legacy, iri=path, result="fail", error=str(exc)))
            continue
        keys = [legacy]
        if legacy.endswith("_NN"):
            count = int(body["FUND_CNT"])
            keys = [legacy[:-3] + f"_{i:02d}" for i in range(1, count + 1)]
        for key in keys:
            target = path
            if legacy.endswith("_NN"):
                index = int(key[-2:]) - 1
                if not dry and not start <= index < start + limit:
                    continue
                target = path.replace("[]", f"[{index - start if not dry else index}]")
            item = dict(field=key, iri=target)
            try:
                value = body[key] if legacy != "none" else None
                expected = transform(value, data["rules"][row["rule"]], data, row, start, limit)
                if dry:
                    item.update(result="transformed", expected=str(expected))
                else:
                    observed = (actual_status if path == "$status" else int(record["contract"])
                                if path == "$request.policyNumber" else read_path(actual, target))
                    if isinstance(expected, Decimal):
                        equal = isinstance(observed, (int, float)) and not isinstance(observed, bool) and Decimal(str(observed)) == expected
                    else:
                        equal = type(observed) is type(expected) and observed == expected
                    item.update(result="pass" if equal else "fail", expected=str(expected), actual=observed)
            except (KeyError, IndexError, ValueError, TypeError) as exc:
                item.update(result="fail", error=str(exc))
            fields.append(item)
    return fields


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--op", required=True, choices=OPERATIONS)
    parser.add_argument("--ns", default="iri")
    parser.add_argument("--dry-run", action="store_true", help="Transform every frozen value without contacting IRI")
    parser.add_argument("--start-index", type=int, default=0)
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()
    if args.start_index < 0 or not 1 <= args.limit <= 200:
        parser.error("start-index >= 0 and 1 <= limit <= 200 required")
    data = lineage()
    responses = []
    for record in records(args.op):
        try:
            if args.dry_run:
                status, body = None, None
            else:
                url = endpoint(base_url(args.ns), args.op, record["contract"])
                if args.op == "funds":
                    url += f"?startIndex={args.start_index}&limit={args.limit}"
                status, body = fetch(url)
            fields = evaluate(record, data, body, status, args.dry_run, args.start_index, args.limit)
            expected_status = data["status_codes"][record["body"]["RTN_CD"]]
            if record["status"] != expected_status:
                fields.append(dict(field="$legacyStatus", result="fail", expected=expected_status, actual=record["status"]))
            if not args.dry_run and args.op == "funds" and status == 200:
                expected_count = max(0, min(args.limit, int(record["body"]["FUND_CNT"]) - args.start_index))
                actual_count = len(body["funds"]) if isinstance(body.get("funds"), list) else -1
                fields.append(dict(field="$arrayLength", result="pass" if expected_count == actual_count else "fail",
                                   expected=expected_count, actual=actual_count))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            fields = [dict(field="$response", result="fail", error=str(exc))]
        responses.append(dict(contract=record["contract"], counts=dict(Counter(f["result"] for f in fields)), fields=fields))
    total = Counter()
    for response in responses:
        total.update(response["counts"])
    summary = dict(total, responses=len(responses),
                   responsesPassed=sum(not r["counts"].get("fail") for r in responses),
                   responsesFailed=sum(bool(r["counts"].get("fail")) for r in responses))
    write_report(args.op, "dry-run" if args.dry_run else "parity",
                 dict(dryRun=args.dry_run, summary=summary, responses=responses))
    return bool(total["fail"])


if __name__ == "__main__":
    raise SystemExit(main())
