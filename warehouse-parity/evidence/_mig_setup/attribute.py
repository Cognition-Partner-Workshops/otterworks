"""Diff two snapshots and attribute every Snowflake session in a time window (read-only).

    python evidence/_mig_setup/attribute.py BEFORE.json AFTER.json START_UTC END_UTC OUT.txt
Lists each session that ran in [START, END] with the harness schemas its statements name in
identifier position (wp.schemas.harness_schemas_used), and every non-read statement that names
an unprefixed DW/STG/AUDIT/PARITY schema.
"""
import json
import sys

from wp import schemas
from wp.engines import connect

READS = {"SELECT", "SHOW", "DESCRIBE", "USE", "ALTER_SESSION"}


def snapshot_diff(before, after):
    b, a = json.load(open(before)), json.load(open(after))
    out = []
    for kind in b:
        def key(r):
            return tuple(str(r[c]) for c in sorted(r) if c.endswith("_schema") or c.endswith("_name")
                         or c == "argument_signature")
        bm, am = {key(r): r for r in b[kind]}, {key(r): r for r in a[kind]}
        for k in sorted(set(bm) | set(am)):
            br, ar = bm.get(k, {}), am.get(k, {})
            changed = {c: (br.get(c), ar.get(c)) for c in sorted(set(br) | set(ar)) if br.get(c) != ar.get(c)}
            if changed:
                out.append(f"{kind} {'.'.join(k)} {changed}")
    return out


def sessions(start, end):
    sf = connect("snowflake")
    _, rows = sf.query(
        "SELECT session_id, start_time, query_type, query_text FROM TABLE(information_schema.query_history("
        f"end_time_range_start => '{start}'::TIMESTAMP_LTZ, result_limit => 10000)) "
        f"WHERE start_time <= '{end}'::TIMESTAMP_LTZ ORDER BY start_time")
    s = {}
    for sid, st, qt, txt in rows:
        d = s.setdefault(sid, {"first": str(st), "last": None, "n": 0, "schemas": set(), "unprefixed_writes": []})
        d["n"] += 1
        d["last"] = str(st)
        used = schemas.harness_schemas_used(txt or "", "MIG_")
        d["schemas"].update(used)
        if qt not in READS and set(used) & set(schemas.SCHEMAS):
            d["unprefixed_writes"].append(f"{st} {qt} {(txt or '')[:100].replace(chr(10), ' ')}")
    return s


def main(before, after, start, end, out):
    lines = ["# snapshot diff (unprefixed DW/STG/AUDIT/PARITY)"]
    lines += snapshot_diff(before, after) or ["IDENTICAL"]
    lines += ["", f"# Snowflake sessions with queries starting in [{start}, {end}]"]
    for sid, d in sorted(sessions(start, end).items(), key=lambda kv: kv[1]["first"]):
        lines.append(f"session {sid} {d['first']} .. {d['last']} statements={d['n']} "
                     f"schemas={','.join(sorted(d['schemas'])) or '-'} unprefixed_writes={len(d['unprefixed_writes'])}")
        lines += [f"    {w}" for w in d["unprefixed_writes"]]
    open(out, "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main(*sys.argv[1:6])
