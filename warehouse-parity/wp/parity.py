"""L1 to L4 parity between the legacy result and the Snowflake result.

L1 row counts, L2 column profiles, L3 per-row hash match by business key,
L4 sampled value diffs. The evidence report is written as JSON and Markdown.
"""
import datetime as dt
import decimal
import hashlib
import json
from pathlib import Path


def canon(v, rtrim=False):
    if v is None:
        return "\\N"
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, (int, decimal.Decimal, float)):
        d = decimal.Decimal(str(v))
        s = format(d.quantize(decimal.Decimal("0.0001")) if d % 1 else d.to_integral_value(), "f")
        return s.rstrip("0").rstrip(".") if "." in s else s
    if isinstance(v, dt.datetime):
        return v.replace(tzinfo=None).isoformat(sep=" ", timespec="milliseconds")
    if isinstance(v, dt.date):
        return v.isoformat()
    s = str(v)
    return s.rstrip() if rtrim else s


def profile(cols, rows, rtrim):
    out = {}
    for i, c in enumerate(cols):
        vals = [r[i] for r in rows]
        nn = [v for v in vals if v is not None]
        p = {"nulls": len(vals) - len(nn), "distinct": len({canon(v, rtrim) for v in nn})}
        if nn:
            nums = [v for v in nn if isinstance(v, (int, float, decimal.Decimal)) and not isinstance(v, bool)]
            if len(nums) == len(nn):
                p.update(min=canon(min(nums)), max=canon(max(nums)), sum=canon(sum(decimal.Decimal(str(x)) for x in nums)))
            else:
                ss = sorted(canon(v, rtrim) for v in nn)
                p.update(min=ss[0], max=ss[-1])
        out[c] = p
    return out


def keyed(cols, rows, keys, rtrim):
    idx = [cols.index(k) for k in keys]
    out = {}
    for r in rows:
        k = tuple(canon(r[i], rtrim) for i in idx)
        vals = [canon(v, rtrim) for v in r]
        out[k] = (hashlib.sha256("\x1f".join(vals).encode()).hexdigest(), dict(zip(cols, vals)))
    return out


def compare(legacy, target, keys, rtrim=False, sample=25):
    lcols, lrows = legacy
    tcols, trows = target
    cols = [c for c in lcols if c in tcols]
    li = [lcols.index(c) for c in cols]
    ti = [tcols.index(c) for c in cols]
    lrows = [tuple(r[i] for i in li) for r in lrows]
    trows = [tuple(r[i] for i in ti) for r in trows]
    res = {"columns": cols, "keys": keys,
           "missing_columns": sorted(set(lcols) ^ set(tcols))}
    res["L1"] = {"legacy": len(lrows), "snowflake": len(trows), "pass": len(lrows) == len(trows)}
    lp, tp = profile(cols, lrows, rtrim), profile(cols, trows, rtrim)
    drift = {c: {"legacy": lp[c], "snowflake": tp[c]} for c in cols if lp[c] != tp[c]}
    res["L2"] = {"pass": not drift, "drift": drift}
    lk, tk = keyed(cols, lrows, keys, rtrim), keyed(cols, trows, keys, rtrim)
    allk = set(lk) | set(tk)
    same = [k for k in allk if k in lk and k in tk and lk[k][0] == tk[k][0]]
    pct = round(100.0 * len(same) / len(allk), 2) if allk else 100.0
    res["L3"] = {"keys": len(allk), "matched": len(same), "match_pct": pct, "pass": pct == 100.0,
                 "only_legacy": len(set(lk) - set(tk)), "only_snowflake": len(set(tk) - set(lk))}
    diffs = []
    for k in sorted(allk - set(same))[:sample]:
        a, b = lk.get(k, (None, {}))[1], tk.get(k, (None, {}))[1]
        if not a or not b:
            diffs.append({"key": list(k), "only_in": "legacy" if a else "snowflake"})
            continue
        diffs.append({"key": list(k), "columns": {c: {"legacy": a[c], "snowflake": b[c]}
                                                  for c in cols if a[c] != b[c]}})
    res["L4"] = {"sampled": len(diffs), "diffs": diffs, "pass": not diffs}
    res["green"] = all(res[x]["pass"] for x in ("L1", "L2", "L3", "L4"))
    return res


def summary_line(res):
    return (f"L1 {'green' if res['L1']['pass'] else 'red'} ({res['L1']['legacy']} vs {res['L1']['snowflake']}), "
            f"L2 {'green' if res['L2']['pass'] else 'red'} ({len(res['L2']['drift'])} columns drift), "
            f"L3 {'green' if res['L3']['pass'] else 'red'} ({res['L3']['match_pct']}% hash match), "
            f"L4 {'green' if res['L4']['pass'] else 'red'} ({res['L4']['sampled']} sampled diffs)")


def write_evidence(obj, label, res, out_dir="evidence"):
    d = Path(out_dir) / obj.replace(".", "_")
    d.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    res = dict(res, object=obj, label=label, at=stamp)
    (d / f"{label}.json").write_text(json.dumps(res, indent=2, default=str))
    md = [f"# Parity: {obj} ({label})", "", f"Run at {stamp}.", "", summary_line(res), "",
          "| Level | Result | Detail |", "|---|---|---|",
          f"| L1 counts | {'green' if res['L1']['pass'] else 'red'} | legacy {res['L1']['legacy']}, snowflake {res['L1']['snowflake']} |",
          f"| L2 profiles | {'green' if res['L2']['pass'] else 'red'} | drift in: {', '.join(res['L2']['drift']) or 'none'} |",
          f"| L3 row hash | {'green' if res['L3']['pass'] else 'red'} | {res['L3']['matched']}/{res['L3']['keys']} keys match ({res['L3']['match_pct']}%) |",
          f"| L4 samples | {'green' if res['L4']['pass'] else 'red'} | {res['L4']['sampled']} diffs sampled |", ""]
    if res["L2"]["drift"]:
        md += ["## L2 drift", "", "| Column | Legacy | Snowflake |", "|---|---|---|"]
        md += [f"| {c} | `{json.dumps(v['legacy'])}` | `{json.dumps(v['snowflake'])}` |" for c, v in res["L2"]["drift"].items()]
        md.append("")
    if res["L4"]["diffs"]:
        md += ["## L4 sampled diffs", "", "| Key | Column | Legacy | Snowflake |", "|---|---|---|---|"]
        for df in res["L4"]["diffs"]:
            if "only_in" in df:
                md.append(f"| {'/'.join(df['key'])} | (row) | {'present' if df['only_in']=='legacy' else 'missing'} | {'present' if df['only_in']=='snowflake' else 'missing'} |")
            for c, v in df.get("columns", {}).items():
                md.append(f"| {'/'.join(df['key'])} | {c} | `{v['legacy']}` | `{v['snowflake']}` |")
        md.append("")
    (d / f"{label}.md").write_text("\n".join(md))
    return d / f"{label}.md"
