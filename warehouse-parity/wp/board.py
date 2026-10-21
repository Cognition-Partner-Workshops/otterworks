"""Wave board. State lives in Snowflake (PARITY.BOARD) so sessions on different machines share it."""
import html
import json
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, urlparse

from . import qlik
from .engines import update_sql

DDL = """CREATE TABLE IF NOT EXISTS PARITY.BOARD (
  object_name VARCHAR, object_type VARCHAR, wave INT, workstream VARCHAR,
  status VARCHAR DEFAULT 'todo', l1 VARCHAR, l2 VARCHAR, l3 VARCHAR, l4 VARCHAR,
  readiness VARCHAR, rules_cited VARCHAR, minutes NUMBER(6,1), pr_url VARCHAR,
  session_url VARCHAR, decision_question VARCHAR, decision_answer VARCHAR, note VARCHAR,
  updated_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP())"""
FIELDS = ["status", "l1", "l2", "l3", "l4", "readiness", "rules_cited", "minutes", "pr_url",
          "session_url", "decision_question", "decision_answer", "note"]
COLOR = {"green": "#1f9d55", "amber": "#d97706", "red": "#dc2626", "in_progress": "#2563eb", "todo": "#6b7280"}


def init(sf, manifest):
    sf.execute("CREATE SCHEMA IF NOT EXISTS PARITY")
    sf.execute(DDL)
    for o in manifest.data["objects"]:
        sf.execute("MERGE INTO PARITY.BOARD b USING (SELECT %s n, %s t, %s w, %s s) x ON b.object_name = x.n "
                   "WHEN NOT MATCHED THEN INSERT (object_name, object_type, wave, workstream) VALUES (x.n, x.t, x.w, x.s)",
                   (o["name"], o["type"], o["wave"], o["workstream"]))


def set_fields(sf, obj, **kw):
    kw = {k: v for k, v in kw.items() if k in FIELDS and v is not None}
    if not kw:
        return
    where = ", updated_at = CURRENT_TIMESTAMP() WHERE LOWER(object_name) = LOWER(%s)"
    n = sf.execute(update_sql("PARITY.BOARD", list(kw), where), (*kw.values(), obj))
    if not n:
        raise SystemExit(f"{obj} is not on the board")


def rows(sf):
    return sf.query("SELECT object_name, object_type, wave, workstream, status, l1, l2, l3, l4, readiness, "
                    "rules_cited, minutes, pr_url, decision_question, decision_answer, note, updated_at "
                    "FROM PARITY.BOARD ORDER BY wave, workstream, object_name")


def rollup(sf):
    cols, rs = rows(sf)
    recs = [dict(zip(cols, r)) for r in rs]
    mins = [float(r["minutes"]) for r in recs if r["minutes"] is not None]
    return {"objects": len(recs),
            "green": [r["object_name"] for r in recs if r["status"] == "green"],
            "needs_decision": [r["object_name"] for r in recs if r["status"] == "amber"],
            "red_or_open": [r["object_name"] for r in recs if r["status"] not in ("green", "amber")],
            "rules_cited": sorted({x.strip() for r in recs for x in (r["rules_cited"] or "").split(",") if x.strip()}),
            "minutes_per_object": round(sum(mins) / len(mins), 1) if mins else None}


STYLE = ("<style>body{font-family:system-ui;margin:24px;color:#111}table{border-collapse:collapse;margin:8px 0 24px}"
         "td,th{border:1px solid #ddd;padding:6px 10px;font-size:14px;text-align:left}th{background:#f3f4f6}"
         ".pill{color:#fff;border-radius:10px;padding:2px 8px;font-size:12px}.eng{font-size:20px;font-weight:600}"
         "td.num{text-align:right;font-variant-numeric:tabular-nums}td.barcell{width:220px}"
         ".bar{background:#2563eb;height:14px;border-radius:2px}.switch a,.switch b{margin-right:12px}"
         ".switch b.on{background:#111;color:#fff;padding:2px 8px;border-radius:4px}h3 small{color:#6b7280;font-weight:400}</style>")


ENGINES = {"sqlserver": "SQL Server (legacy SQL)", "snowflake": "Snowflake (converted SQL)"}


def report_object(manifest, name=None):
    """The manifest's report_object may be an object name or the path of its legacy script."""
    name = name or manifest.data["report_object"]
    hit = [o for o in manifest.data["objects"] if name in (o.get("legacy_script"), o.get("target_script"))]
    return hit[0] if hit else manifest.obj(name)


def _bar_table(cols, rs, measure):
    i = cols.index(measure) if measure in cols else None
    top = max((abs(float(r[i])) for r in rs if r[i] is not None), default=0) if i is not None else 0
    head = "".join(f"<th>{html.escape(c)}</th>" for c in cols) + ("<th></th>" if i is not None else "")
    body = []
    for r in rs:
        cells = "".join(f"<td class=num>{html.escape(str(v))}</td>" if isinstance(v, (int, float, Decimal))
                        else f"<td>{html.escape(str(v if v is not None else ''))}</td>" for v in r)
        if i is not None:
            w = 0 if not top or r[i] is None else abs(float(r[i])) / top * 100
            cells += f"<td class=barcell><div class=bar style='width:{w:.1f}%'></div></td>"
        body.append(f"<tr>{cells}</tr>")
    return f"<table><tr>{head}</tr>{''.join(body)}</table>"


def report(manifest, eng, engine, object_name=None):
    if engine not in ENGINES:
        raise SystemExit(f"unknown engine {engine}")
    obj = report_object(manifest, object_name)
    script = manifest.file(obj["legacy_script"] if engine == "sqlserver" else obj["target_script"])
    bars = {**{b: m[0] for b, m in (obj.get("measures") or {}).items()}, **(obj.get("report_bars") or {})}
    switch = " ".join(f"<b class=on>{label}</b>" if e == engine else
                      f"<a href='/report?engine={e}&object={quote(obj['name'])}'>{label}</a>"
                      for e, label in ENGINES.items())
    parts = [f"<html><head><title>{html.escape(obj['name'])} on {engine}</title>{STYLE}</head><body>",
             f"<div class=eng>Producer dashboard on {ENGINES[engine]}</div>",
             f"<p class=switch>Engine: {switch}</p>",
             (f"<p>Frozen window {manifest.data['frozen_window']['start']} to {manifest.data['frozen_window']['end']}. "
              f"Script: {html.escape(str(script.relative_to(manifest.root)))}</p>")]
    for block, (cols, rs) in qlik.run(eng(engine), script).items():
        keys = [cols.index(k) for k in (obj.get("compare_blocks") or {}).get(block, []) if k in cols]
        rs = sorted(rs, key=lambda r: tuple(str(r[k]) for k in keys))
        parts.append(f"<h3>{html.escape(block)} <small>{len(rs)} rows</small></h3>" + _bar_table(cols, rs, bars.get(block)))
    return "".join(parts) + "</body></html>"


def serve(manifest, port=8765, engines=None):
    from .engines import connect
    cache = {}

    def eng(name):
        if name not in cache:
            cache[name] = (engines or {}).get(name) or connect(name)
        return cache[name]

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, body, ctype="text/html"):
            data = body.encode()
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            u = urlparse(self.path)
            q = parse_qs(u.query)
            if u.path == "/report":
                return self._send(report(manifest, eng, q.get("engine", ["sqlserver"])[0], q.get("object", [None])[0]))
            if u.path == "/rollup.json":
                return self._send(json.dumps(rollup(eng("snowflake")), default=str), "application/json")
            cols, rs = rows(eng("snowflake"))
            ru = rollup(eng("snowflake"))
            pills = [[*r[:4], f"<span class=pill style='background:{COLOR.get(r[4], '#6b7280')}'>{r[4]}</span>", *r[5:]] for r in rs]
            head = "".join(f"<th>{c}</th>" for c in cols)
            body = "".join("<tr>" + "".join(f"<td>{v if i == 4 else html.escape(str(v if v is not None else ''))}</td>"
                                            for i, v in enumerate(r)) + "</tr>" for r in pills)
            self._send(f"<html><head><title>Parity board</title>{STYLE}</head><body><h2>Parity wave board</h2>"
                       f"<p>{len(ru['green'])} green, {len(ru['needs_decision'])} need a decision, "
                       f"{len(ru['red_or_open'])} open, {ru['minutes_per_object']} minutes per object. "
                       f"<a href='/report?engine=sqlserver'>Report on SQL Server</a> | "
                       f"<a href='/report?engine=snowflake'>Report on Snowflake</a></p>"
                       f"<table><tr>{head}</tr>{body}</table></body></html>")

    print(f"board on http://localhost:{port}")
    ThreadingHTTPServer(("0.0.0.0", port), H).serve_forever()
