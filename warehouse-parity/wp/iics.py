"""Run the SQL inside an IICS mapping export: pre-SQL, source override, lookup, target, post-SQL."""
import csv
import json
from pathlib import Path


def _params(mapping, param_file=None):
    vals = {p["name"]: p.get("default", "") for p in mapping.get("parameters", [])}
    if param_file:
        for line in Path(param_file).read_text().splitlines():
            if line.startswith("$$") and "=" in line:
                k, v = line.split("=", 1)
                vals[k.strip()] = v.strip()
    return vals


def _sub(sql, vals):
    for k in sorted(vals, key=len, reverse=True):
        sql = sql.replace(k, vals[k])
    return sql


def extract(path, param_file=None):
    m = json.loads(Path(path).read_text())
    vals = _params(m, param_file)
    steps = {"name": m["name"], "connection": None, "pre": [], "source": None, "lookups": [], "target": None, "post": []}
    for t in m["transformations"]:
        steps["connection"] = steps["connection"] or _sub(t.get("connection", ""), vals)
        if t.get("preSQL"):
            steps["pre"].append(_sub(t["preSQL"], vals))
        if t["type"] == "Source":
            steps["source"] = _sub(t["sqlOverride"], vals)
        elif t["type"] == "Lookup":
            steps["lookups"].append({"name": t["name"], "sql": _sub(t["lookupSqlOverride"], vals),
                                     "condition": t["condition"], "return": t["returnPort"]})
        elif t["type"] == "Target":
            steps["target"] = {"object": t["object"], "fieldMap": t["fieldMap"]}
        if t.get("postSQL"):
            steps["post"].append(_sub(t["postSQL"], vals))
    return steps


def run(engine, path, param_file=None, export_dir=None):
    s = extract(path, param_file)
    for sql in s["pre"]:
        engine.execute(sql)
    cols, rows = engine.query(s["source"])
    recs = [dict(zip(cols, r)) for r in rows]
    exports = {"source": (cols, rows)}
    for lk in s["lookups"]:
        lcols, lrows = engine.query(lk["sql"])
        exports[lk["name"]] = (lcols, lrows)
        left, right = [x.strip().lower() for x in lk["condition"].split("=")]
        in_port = right[3:] if right.startswith("in_") else right
        table = {}
        for r in lrows:
            d = dict(zip(lcols, r))
            table.setdefault(d[left], d[lk["return"].lower()])
        for rec in recs:
            rec[f"{lk['name'].lower()}.{lk['return'].lower()}"] = table.get(rec[in_port])
    fm = s["target"]["fieldMap"]
    tcols = list(fm)
    trows = [tuple(rec[fm[c].lower()] for c in tcols) for rec in recs]
    engine.insert_rows(s["target"]["object"], tcols, trows)
    for sql in s["post"]:
        engine.execute(sql)
    if export_dir:
        d = Path(export_dir)
        d.mkdir(parents=True, exist_ok=True)
        for name, (c, r) in exports.items():
            with open(d / f"{s['name']}.{name}.{engine.name}.csv", "w", newline="") as fh:
                w = csv.writer(fh)
                w.writerow(c)
                w.writerows(r)
    return {"mapping": s["name"], "connection": s["connection"], "source_rows": len(rows), "target_rows": len(trows)}
