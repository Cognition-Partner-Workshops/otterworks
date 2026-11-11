# ruff: noqa: E501  (HTML and Tableau XML templates)
"""Turn gate/out/bi/data/*.json into the report parity console (static HTML)."""

from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any

import yaml

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "out" / "bi"
SPEC = HERE / "workbooks.yaml"

COLORS = {
    "PASS": "#1a7f37",
    "DIVERGE": "#cf222e",
    "PENDING": "#9a6700",
    "NOT REPOINTED": "#9a6700",
    "NOT MIGRATED": "#57606a",
    "NOT RUN": "#8c959f",
}
LABELS = {
    "PASS": "Parity",
    "DIVERGE": "Differs",
    "PENDING": "Pending",
    "NOT REPOINTED": "Still on SQL Server",
    "NOT MIGRATED": "On SQL Server",
    "NOT RUN": "Not run",
}

CSS = """
*{box-sizing:border-box}body{margin:0;font:14px/1.45 -apple-system,Segoe UI,Helvetica,Arial,sans-serif;color:#1f2328;background:#f6f8fa}
header{background:#1f2a44;color:#fff;padding:18px 28px;display:flex;align-items:center;gap:18px}
header h1{font-size:20px;margin:0;font-weight:600}header .sub{opacity:.75}header a{color:#9ecbff}
main{padding:22px 28px;max-width:1500px;margin:auto}
.chip{display:inline-block;padding:2px 10px;border-radius:12px;color:#fff;font-weight:600;font-size:12px;white-space:nowrap}
.score{display:flex;gap:14px;margin:4px 0 22px}.score div{background:#fff;border:1px solid #d0d7de;border-radius:8px;padding:12px 18px;min-width:150px}
.score b{font-size:26px;display:block}
.folder{margin:18px 0 6px;font-weight:600;color:#57606a;text-transform:uppercase;font-size:12px;letter-spacing:.06em}
.tiles{display:grid;grid-template-columns:repeat(auto-fill,minmax(270px,1fr));gap:12px}
.tile{display:block;background:#fff;border:1px solid #d0d7de;border-left:6px solid;border-radius:8px;padding:12px 14px;color:inherit;text-decoration:none}
.tile:hover{box-shadow:0 2px 8px rgba(0,0,0,.12)}.tile h3{margin:0 0 6px;font-size:15px}.tile .meta{color:#57606a;font-size:12px}
.card{background:#fff;border:1px solid #d0d7de;border-radius:8px;margin:0 0 18px;overflow:hidden}
.card>h2{margin:0;padding:10px 16px;font-size:15px;border-bottom:1px solid #d0d7de;display:flex;justify-content:space-between;align-items:center;background:#f6f8fa}
.pair{display:grid;grid-template-columns:1fr 1fr}.pane{padding:12px 16px}.pane+.pane{border-left:1px solid #d0d7de}
.pane h4{margin:0 0 8px;font-size:12px;text-transform:uppercase;letter-spacing:.05em;color:#57606a}
.empty{color:#8c959f;padding:30px 0;text-align:center}
table{border-collapse:collapse;width:100%;font-size:12px}th,td{padding:4px 8px;border-bottom:1px solid #eaeef2;text-align:left}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}td.bad{background:#ffebe9;color:#a40e26;font-weight:600}
pre{margin:0;padding:10px;background:#f6f8fa;border:1px solid #eaeef2;border-radius:6px;white-space:pre-wrap;font-size:12px}
.lineage{display:flex;flex-wrap:wrap;gap:6px;align-items:center;padding:12px 16px}.lineage .arrow{color:#8c959f}
.unit{border:1px solid;border-radius:6px;padding:2px 8px;font-size:12px;font-family:ui-monospace,monospace}
.bad-text{color:#cf222e;font-weight:600}.ok-text{color:#1a7f37;font-weight:600}
"""

LIVE = (
    "<script>if(location.search.includes('live')){setTimeout(()=>location.reload(),4000);"
    "addEventListener('DOMContentLoaded',()=>document.querySelectorAll('a[href$=\".html\"]')"
    ".forEach(a=>a.href+=location.search))}</script>"
)


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def fmt(value: Any) -> str:
    if value is None:
        return "–"
    if isinstance(value, float):
        return (
            f"{value:,.0f}"
            if value == int(value) and abs(value) < 1e15
            else f"{value:,.4f}".rstrip("0")
        )
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)


def chip(status: str) -> str:
    return f"<span class='chip' style='background:{COLORS.get(status, '#57606a')}'>{esc(LABELS.get(status, status))}</span>"


def page(title: str, body: str, back: bool = False) -> str:
    nav = "<a href='index.html'>&larr; All workbooks</a>" if back else ""
    return (
        f"<!doctype html><html><head><meta charset='utf-8'><title>{esc(title)}</title><style>{CSS}</style></head><body>"
        f"<header><div><h1>{esc(title)}</h1><div class='sub'>Tableau estate · SQL Server to Snowflake · report parity</div></div>"
        f"<div style='margin-left:auto'>{nav}</div></header><main>{body}</main>{LIVE}</body></html>"
    )


def bars(sheet: dict[str, Any], side: str) -> str:
    rows = [r for r in sheet["rows"] if r[side] is not None] if side == "legacy" else sheet["rows"]
    measure = sheet["measures"][0]
    values = [abs(r[s][measure]) for r in sheet["rows"] for s in ("legacy", "target") if r[s]]
    top = max(values or [1]) or 1
    if side == "target" and not any(r["target"] for r in rows):
        return ""
    out, y = [], 0
    for row in rows:
        data = row[side]
        bad = side == "target" and measure in row["diff"]
        width = 0 if data is None else 220 * abs(data[measure]) / top
        label = row["label"] if len(row["label"]) <= 30 else row["label"][:29] + "…"
        value = "missing" if data is None else fmt(data[measure])
        if bad and row["legacy"] is not None:
            value += f"  (SQL Server {fmt(row['legacy'][measure])})"
        fill = "#cf222e" if bad else "#4e79a7"
        out.append(
            f"<text x='0' y='{y + 13}' font-size='11'>{esc(label)}</text>"
            f"<rect x='190' y='{y + 3}' width='{width:.1f}' height='13' fill='{fill}' rx='2'/>"
            f"<text x='{196 + width:.1f}' y='{y + 13}' font-size='11' fill='{'#cf222e' if bad else '#1f2328'}'"
            f"{' font-weight="600"' if bad else ''}>{esc(value)}</text>"
        )
        y += 19
    return f"<svg width='100%' viewBox='0 0 640 {max(y, 20)}' preserveAspectRatio='xMinYMin meet'>{''.join(out)}</svg>"


def line(sheet: dict[str, Any], side: str) -> str:
    measure = sheet["measures"][0]
    rows = sheet["rows"]
    if side == "target" and not any(r["target"] for r in rows):
        return ""
    values = [r[s][measure] for r in rows for s in ("legacy", "target") if r[s]]
    if not values:
        return ""
    low, high = min(values), max(values)
    span = (high - low) or 1
    points, marks = [], []
    for index, row in enumerate(rows):
        data = row[side]
        if data is None:
            continue
        x = 40 + 580 * index / max(len(rows) - 1, 1)
        y = 170 - 150 * (data[measure] - low) / span
        points.append(f"{x:.1f},{y:.1f}")
        if side == "target" and measure in row["diff"]:
            marks.append(f"<circle cx='{x:.1f}' cy='{y:.1f}' r='4' fill='#cf222e'/>")
    first, last = rows[0]["label"], rows[-1]["label"]
    return (
        f"<svg width='100%' viewBox='0 0 640 200'><polyline fill='none' stroke='#4e79a7' stroke-width='2' points='{' '.join(points)}'/>"
        f"{''.join(marks)}<text x='40' y='192' font-size='11'>{esc(first)}</text><text x='620' y='192' font-size='11' text-anchor='end'>{esc(last)}</text>"
        f"<text x='0' y='20' font-size='11'>{esc(fmt(high))}</text><text x='0' y='170' font-size='11'>{esc(fmt(low))}</text></svg>"
    )


def text_table(sheet: dict[str, Any], side: str) -> str:
    if side == "target" and not any(r["target"] for r in sheet["rows"]):
        return ""
    head = " / ".join(sheet["dimensions"])
    cols = "".join(f"<th class='num'>{esc(m.split(':', 1)[1])}</th>" for m in sheet["measures"])
    body = []
    for row in sheet["rows"]:
        data = row[side]
        cells = []
        for measure in sheet["measures"]:
            bad = side == "target" and measure in row["diff"]
            value = "missing" if data is None else fmt(data[measure])
            hint = (
                f" title='SQL Server: {esc(fmt((row['legacy'] or {}).get(measure)))}'"
                if bad
                else ""
            )
            cells.append(f"<td class='num{' bad' if bad else ''}'{hint}>{esc(value)}</td>")
        body.append(f"<tr><td>{esc(row['label'])}</td>{''.join(cells)}</tr>")
    return f"<table><tr><th>{esc(head)}</th>{cols}</tr>{''.join(body)}</table>"


def sheet_card(sheet: dict[str, Any], migrated: bool) -> str:
    draw = {"Bar": bars, "Line": line}.get(sheet["mark"], text_table)
    legacy = draw(sheet, "legacy") or "<div class='empty'>No rows for this date</div>"
    if migrated:
        target = (
            draw(sheet, "target") or "<div class='empty'>Snowflake has not returned rows yet</div>"
        )
    else:
        target = "<div class='empty'>Not migrated yet: this sheet still reads SQL Server</div>"
    if not migrated:
        badge = ""
    elif sheet["differing_marks"]:
        badge = f"<span class='bad-text'>{sheet['differing_marks']} of {sheet['marks']} marks differ</span>"
    elif any(r["target"] for r in sheet["rows"]):
        badge = f"<span class='ok-text'>All {sheet['marks']} marks match</span>"
    else:
        badge = ""
    return (
        f"<div class='card'><h2><span>{esc(sheet['name'])} <span style='color:#57606a;font-weight:400'>· {esc(sheet['mark'])} · {esc(sheet['datasource'])}</span></span>{badge}</h2>"
        f"<div class='pair'><div class='pane'><h4>SQL Server · legacy</h4>{legacy}</div>"
        f"<div class='pane'><h4>Snowflake · migrated</h4>{target}</div></div></div>"
    )


def datasource_card(ds: dict[str, Any]) -> str:
    rows = (
        f"{fmt(ds['legacy_rows'])} rows on SQL Server · {fmt(ds['target_rows'])} rows on Snowflake"
    )
    detail = (
        f"<div style='padding:8px 16px;color:#9a6700'>{esc(ds['message'])}</div>"
        if ds.get("message")
        else ""
    )
    diffs = ""
    if ds.get("diffs"):
        keys = ds["keys"]
        head = "".join(f"<th>{esc(k)}</th>" for k in keys)
        body = "".join(
            "<tr>"
            + "".join(f"<td>{esc(d['key'].get(k))}</td>" for k in keys)
            + f"<td>{esc(d['column'])}</td><td class='num'>{esc(fmt(d['sqlserver']))}</td><td class='num bad'>{esc(fmt(d['snowflake']))}</td></tr>"
            for d in ds["diffs"][:60]
        )
        diffs = (
            f"<div class='pane'><h4>{ds['differing_keys']} rows differ, {ds.get('diff_cells', len(ds['diffs']))} cells</h4>"
            f"<table><tr>{head}<th>column</th><th class='num'>SQL Server</th><th class='num'>Snowflake</th></tr>{body}</table></div>"
        )
    connection = ds.get("connection") or {}
    conn = " · ".join(f"{k}={v}" for k, v in connection.items() if v)
    target_sql = esc(ds["target_sql"]) if ds.get("target_sql") else "not written yet"
    return (
        f"<div class='card'><h2><span>Datasource: {esc(ds['caption'])} <span style='color:#57606a;font-weight:400'>· from {esc(ds['report'])}.rdl · keys {esc(', '.join(ds['keys']))}</span></span>{chip(ds['status'])}</h2>"
        f"<div style='padding:8px 16px;color:#57606a'>{rows}{(' · ' + esc(conn)) if conn else ''}</div>{detail}"
        f"<div class='pair'><div class='pane'><h4>Custom SQL · T-SQL</h4><pre>{esc(ds['legacy_sql'])}</pre></div>"
        f"<div class='pane'><h4>Custom SQL · Snowflake</h4><pre>{target_sql}</pre></div></div>{diffs}</div>"
    )


def workbook_page(data: dict[str, Any]) -> str:
    migrated = data["status"] not in {"NOT MIGRATED"}
    units = "<span class='arrow'>→</span>".join(
        f"<span class='unit' style='border-color:{COLORS[u['status']]};color:{COLORS[u['status']]}'>{esc(u['unit'])} · {esc(u['status'])}</span>"
        for u in data["units"]
    )
    lineage = (
        f"<div class='card'><h2><span>Lineage: legacy procedures behind this workbook (dbt unit status from the parity ledger)</span></h2>"
        f"<div class='lineage'>{units}<span class='arrow'>→</span><span class='unit' style='border-color:#57606a'>{esc(', '.join(data['legacy_tables']))}</span>"
        f"<span class='arrow'>→</span><span class='unit' style='border-color:#57606a'>{esc(data['file'])}</span></div></div>"
    )
    header = (
        f"<div style='display:flex;gap:14px;align-items:center;margin-bottom:14px'>{chip(data['status'])}"
        f"<span style='color:#57606a'>Business date {esc(data['date'])} · run {esc(data['run'])} · checked {esc(data['generated_at'])}</span></div>"
    )
    body = (
        header
        + lineage
        + "".join(sheet_card(s, migrated) for s in data["sheets"])
        + "".join(datasource_card(d) for d in data["datasources"])
    )
    return page(data["workbook"], body, back=True)


def render() -> None:
    spec = yaml.safe_load(SPEC.read_text())
    results = {}
    for entry in spec["workbooks"]:
        path = OUT / "data" / f"{slug(entry['name'])}.json"
        results[entry["name"]] = json.loads(path.read_text()) if path.exists() else None
    OUT.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    folders: dict[str, list[str]] = {}
    for entry in spec["workbooks"]:
        data = results[entry["name"]]
        status = data["status"] if data else "NOT RUN"
        counts[status] = counts.get(status, 0) + 1
        if data:
            (OUT / f"{slug(entry['name'])}.html").write_text(workbook_page(data))
            sheets = len(data["sheets"])
            bad = sum(s["differing_marks"] for s in data["sheets"])
            meta = f"{data['date']} · {sheets} sheets · {len(entry['datasources'])} datasources" + (
                f" · <span class='bad-text'>{bad} marks differ</span>" if bad else ""
            )
            link = f"{slug(entry['name'])}.html"
        else:
            meta, link = "run make sfm-bi-parity", "#"
        folders.setdefault(entry["folder"], []).append(
            f"<a class='tile' href='{link}' style='border-left-color:{COLORS[status]}'><h3>{esc(entry['name'])}</h3>"
            f"{chip(status)} <span class='meta'>{meta}</span><div class='meta'>{esc(', '.join(entry['legacy_tables']))}</div></a>"
        )
    dates = sorted({d["date"] for d in results.values() if d})
    mixed = (
        " <span class='bad-text'>· mixed dates, run make sfm-bi-parity without WORKBOOK to refresh all</span>"
        if len(dates) > 1
        else ""
    )
    score = "".join(
        f"<div><b style='color:{COLORS[s]}'>{counts.get(s, 0)}</b>{esc(LABELS[s])}</div>"
        for s in ["PASS", "DIVERGE", "PENDING", "NOT REPOINTED", "NOT MIGRATED", "NOT RUN"]
        if counts.get(s) or s in {"PASS", "NOT MIGRATED"}
    )
    body = (
        f"<div style='color:#57606a;margin-bottom:8px'>{len(spec['workbooks'])} workbooks · business date {esc(', '.join(dates) or 'not run')}{mixed}</div>"
        f"<div class='score'>{score}</div>"
        + "".join(
            f"<div class='folder'>{esc(folder)}</div><div class='tiles'>{''.join(tiles)}</div>"
            for folder, tiles in folders.items()
        )
    )
    (OUT / "index.html").write_text(page("Tableau migration parity", body))


if __name__ == "__main__":
    render()
