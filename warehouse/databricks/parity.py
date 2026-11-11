"""Exact stored-value parity, with tagged SQL and persistent rung receipts.

Specs contain an ``objects`` list of {"object": "billing__invoice_hdr",
"keys": ["invoice_id"]}; optional ``columns`` selects compared columns.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re

from .baseline import literal
from .sql import Warehouse, identifier


COMMENT = "run_token=dbx-d1111 expires=2026-11-24"
RESULTS = "cpw.dbx_d1111_parity.results"
DOCUMENT_VERSION = "billing__in_documents_doc_version"
RAW_DIFFERENCE = "observed raw baseline difference (nondeterministic source tie)"


def raw_rung(metric):
    return f"{RAW_DIFFERENCE}: {metric}"


def relation(schema, name):
    return f"cpw.{schema}.{identifier(name)}"


def describe(client, table):
    result = client.execute(f"DESCRIBE TABLE {table}", step="parity-profile")
    return {row[0].lower(): row[1].lower() for row in result["rows"]
            if row[0] and not row[0].startswith("#") and row[1]}


def numeric(data_type):
    return bool(re.match(r"^(?:tinyint|smallint|int|bigint|decimal|float|double)", data_type))


def canonical(column, data_type):
    value = f"CAST({identifier(column)} AS STRING)"
    if re.match(r"^(?:decimal|tinyint|smallint|int|bigint)", data_type):
        value = f"regexp_replace(regexp_replace({value}, '(\\\\.[0-9]*?)0+$', '$1'), '\\\\.$', '')"
    return value


def encoded(columns, types):
    # JSON arrays distinguish NULL, empty strings, delimiters and trailing spaces.
    return "to_json(array(" + ",".join(canonical(c, types[c]) for c in columns) + "))"


def grouped(table, columns, keys, types):
    return (f"SELECT {encoded(keys, types)} AS k, "
            f"sort_array(collect_list(sha2({encoded(columns, types)},256))) AS hashes, "
            f"sort_array(collect_list({encoded(columns, types)})) AS vals "
            f"FROM {table} GROUP BY {encoded(keys, types)}")


def hash_join(before, after, columns, keys, types):
    return (f"WITH b AS ({grouped(before, columns, keys, types)}), "
            f"a AS ({grouped(after, columns, keys, types)}) "
            "SELECT coalesce(b.k,a.k) AS key, "
            "CASE WHEN b.k IS NULL THEN 'missing_before' WHEN a.k IS NULL THEN 'missing_after' "
            "ELSE 'different_hash' END AS difference, b.vals AS before_values, a.vals AS after_values "
            "FROM b FULL OUTER JOIN a ON b.k=a.k WHERE b.k IS NULL OR a.k IS NULL OR b.hashes<>a.hashes")


def profile(table, columns, types):
    selects = []
    for column in columns:
        c = identifier(column)
        total = f"SUM({c})" if numeric(types[column]) else f"SUM(length({c}))" if types[column].startswith(("string", "varchar", "char")) else "NULL"
        selects.append(f"SELECT {literal(column)} AS col, COUNT({c}) AS non_null, "
                       f"COUNT(DISTINCT {c}) AS distinct_values, "
                       f"CAST(MIN({c}) AS STRING) AS min_value, CAST(MAX({c}) AS STRING) AS max_value, "
                       f"CAST({total} AS STRING) AS total FROM {table}")
    return " UNION ALL ".join(selects)


def normalize_profile(rows, types):
    from decimal import Decimal

    values = {}
    for row in rows:
        column, *metrics = row
        if numeric(types[column]):
            metrics = [Decimal(str(v)) if v is not None else None for v in metrics]
        values[column] = metrics
    return values


def samples(rows, columns):
    result = []
    for key, difference, before, after in rows:
        before = json.loads(before) if isinstance(before, str) else before
        after = json.loads(after) if isinstance(after, str) else after
        b = [json.loads(v) for v in (before or [])]
        a = [json.loads(v) for v in (after or [])]
        diffs = {}
        for i, column in enumerate(columns):
            bv, av = [r[i] for r in b], [r[i] for r in a]
            if bv != av:
                diffs[column] = {"before": bv, "after": av}
        result.append({"key": json.loads(key), "difference": difference, "columns": diffs})
    return result


def compare(client, spec, sample_size=10):
    name, keys = spec["object"], spec["keys"]
    if not keys or sample_size < 1:
        raise ValueError("nonempty keys and positive sample_size are required")
    before = relation("dbx_d1111_before", spec.get("before", name))
    after = relation("dbx_d1111_after", name)
    types, after_types = describe(client, before), describe(client, after)
    columns = spec.get("columns", list(types))
    if not columns or not set(keys) <= set(columns):
        raise ValueError("keys must be included in compared columns")
    if not set(columns) <= types.keys() or not set(columns) <= after_types.keys():
        raise ValueError("compared columns must exist on both sides")
    results = []
    def rung(name, response, passed, detail):
        observed = spec['object'] == DOCUMENT_VERSION and name in {'profile', 'hash', 'sample'}
        if observed:
            detail = {'measurement': name, 'raw_comparison_status': 'pass' if passed else 'fail',
                      'interpretation': RAW_DIFFERENCE, 'measured_values': detail}
        results.append({"object": spec["object"], "rung": name,
                        "status": "observed" if observed else "pass" if passed else "fail", "detail": detail,
                        "statement_id": response["statement_id"]})
        if observed:
            results[-1]['rung'] = raw_rung(name)
    count = client.execute(f"SELECT (SELECT COUNT(*) FROM {before}), (SELECT COUNT(*) FROM {after})", step="parity-count")
    b, a = count["rows"][0]
    rung("count", count, int(b) == int(a), {"before": b, "after": a})
    profiles = client.execute(f"SELECT 'before' AS side,* FROM ({profile(before, columns, types)}) "
                              f"UNION ALL SELECT 'after' AS side,* FROM ({profile(after, columns, types)})", step="parity-profile")
    bp = normalize_profile([r[1:] for r in profiles["rows"] if r[0] == "before"], types)
    ap = normalize_profile([r[1:] for r in profiles["rows"] if r[0] == "after"], types)
    differences = {c: {"before": bp[c], "after": ap[c]} for c in columns if bp[c] != ap[c]}
    rung("profile", profiles, not differences, differences)
    query = hash_join(before, after, columns, keys, types)
    hashes = client.execute(query + " ORDER BY key", step="parity-hash")
    rung("hash", hashes, not hashes["rows"], {"different_keys": len(hashes["rows"]), "keys": [r[:2] for r in hashes["rows"]]})
    sample = client.execute(query + f" ORDER BY key LIMIT {int(sample_size)}", step="parity-sample")
    rung("sample", sample, not sample["rows"], samples(sample["rows"], columns))
    return results


def run(client, label, spec, evidence_dir=None, *, replace=False):
    directory = Path(evidence_dir or Path.home() / "dbx-evidence")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", label):
        raise ValueError("invalid run label")
    client.execute(f"CREATE SCHEMA IF NOT EXISTS cpw.dbx_d1111_parity COMMENT '{COMMENT}'", step="parity-results")
    client.execute(f"CREATE TABLE IF NOT EXISTS {RESULTS} (run_label STRING, object STRING, rung STRING, "
                   f"status STRING, detail STRING, statement_id STRING, measured_at TIMESTAMP) USING DELTA COMMENT '{COMMENT}'", step="parity-results")
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"parity_{label}.json"
    results = json.loads(path.read_text()) if path.exists() else []
    for obj in spec["objects"]:
        if replace:
            replaced_rungs = {'count', 'profile', 'hash', 'sample'}
            if obj['object'] == DOCUMENT_VERSION:
                replaced_rungs.update(raw_rung(r) for r in ('profile', 'hash', 'sample'))
            legacy = [r for r in results if obj.get('before') == r['object'] and r['rung'] in {'count','profile','hash','sample'}]
            if legacy and label == 'v1-direct':
                ids = ','.join(literal(r['statement_id']) for r in legacy)
                client.execute(f"DELETE FROM {RESULTS} WHERE run_label={literal(label)} AND object={literal(obj['before'])} "
                               f"AND statement_id IN ({ids})", step="parity-results")
                results = [r for r in results if r not in legacy]
            client.execute(f"DELETE FROM {RESULTS} WHERE run_label={literal(label)} AND object={literal(obj['object'])} "
                           f"AND rung IN ({','.join(literal(r) for r in sorted(replaced_rungs))})", step="parity-results")
            results = [r for r in results if not (r['object'] == obj['object'] and r['rung'] in replaced_rungs)]
        for row in compare(client, obj, spec.get("sample_size", 10)):
            row.update(run_label=label, measured_at=datetime.now(timezone.utc).isoformat())
            detail = json.dumps(row["detail"], default=str)
            values = [label, row["object"], row["rung"], row["status"], detail, row["statement_id"]]
            stored = client.execute(f"INSERT INTO {RESULTS} VALUES (" + ",".join(literal(v) for v in values) + ",current_timestamp())", step="parity-results")
            row["receipt_statement_id"] = stored["statement_id"]
            results.append(row)
            path.write_text(json.dumps(results, indent=2, default=str))
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", required=True)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--object", action="append")
    parser.add_argument("--replace", action="store_true")
    parser.add_argument("--gaps", action="store_true")
    args = parser.parse_args()
    client = Warehouse(act="prove", consumer="billing")
    spec = json.loads(args.spec.read_text())
    if args.object:
        spec['objects'] = [o for o in spec['objects'] if o['object'] in args.object]
    results = run(client, args.label, spec, replace=args.replace)
    if args.gaps:
        from .gaps import run_gaps
        results.extend(run_gaps(client, args.label, objects=args.object))
    for row in results:
        print(row["object"], row["rung"], row["status"], row["statement_id"])


if __name__ == "__main__":
    main()
