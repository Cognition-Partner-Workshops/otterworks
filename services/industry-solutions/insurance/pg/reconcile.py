"""Reconcile the PostgreSQL 16 copy of Commission Pay against Oracle.

Every table and the summary MV are compared row by row (primary key, every
column, exact values) and by control figures; the ledger is totalled per agent
and per period to the cent; the live Oracle figures are checked against the
pinned golden baseline; the translated schema and its constraint behaviour are
compared object by object. Writes reports/reconciliation.{md,json} and exits
non-zero if any row is red.
"""

from __future__ import annotations

import json
import sys
from decimal import Decimal
from pathlib import Path

import oracledb
import psycopg

from common import (
    LEDGER,
    RATES,
    RELATIONS,
    control_metrics,
    fetch_rows,
    oracle_columns,
    oracle_connect,
    pg_connect,
    query,
)

HERE = Path(__file__).parent
GOLDEN = HERE / "golden" / "oracle_baseline.json"
REPORTS = HERE / "reports"

OK, RED, ACCEPTED, INFO = "MATCH", "MISMATCH", "ACCEPTED", "INFO"

# Divergences decided by Commission Pay owners. A probe whose outcomes differ
# is red until its decision is recorded here.
DECISIONS: dict[str, str] = {
    "D1": "A, plain identity; an explicit NULL id is rejected",
    "D2": "A, varchar(n) counts characters",
    "D3": "B, CHECK (col <> '') on NOT NULL strings",
    "D4": "A, commission_amount reproduces Oracle NUMBER arithmetic",
    "D5": "A, bare NUMBER id columns are bigint",
}

STRING_MAX = "ñ" * 120  # 120 characters, 240 bytes in AL32UTF8 / UTF8

# (id, decision, what is probed, statements). Statements run in order inside a
# transaction that is always rolled back; a SELECT's result is the outcome.
PROBES = [
    ("P1", "D1", "identity column given an explicit NULL (agents.agent_id)",
     [("INSERT INTO commission_pay.agents (agent_id, agent_code, full_name, license_no)"
      " VALUES (NULL, 'PRB-1', 'Probe', 'LIC-PRB-1')")]),
    ("P2", "D2", "120 characters / 240 bytes into products.product_name VARCHAR2(120)",
     [(("INSERT INTO commission_pay.products (product_code, product_name, line_of_business)"
       " VALUES ('PRB-2', {s}, 'AUTO')"), STRING_MAX)]),
    ("P3", "D3", "empty string into NOT NULL products.product_name",
     [("INSERT INTO commission_pay.products (product_code, product_name, line_of_business)"
      " VALUES ('PRB-3', '', 'AUTO')")]),
    ("P4", None, "second closed rate in one product/agent scope (ux_rates_open)",
     [("INSERT INTO commission_pay.commission_rates (product_code, agent_id, rate_pct, effective_from,"
      " effective_to, created_by) VALUES ('TERM-20', NULL, 12, DATE '2020-01-01', DATE '2020-12-31', 'probe')"),
      ("INSERT INTO commission_pay.commission_rates (product_code, agent_id, rate_pct, effective_from,"
      " effective_to, created_by) VALUES ('TERM-20', NULL, 13, DATE '2021-01-01', DATE '2021-12-31', 'probe')")]),
    ("P5", None, "NUMBER(12,2) / numeric(12,2) rounding on insert of 1000.005 and 1000.0049",
     [("INSERT INTO commission_pay.policies (policy_id, policy_no, product_code, holder_name, annual_premium,"
      " issued_date) VALUES (901, 'PRB-5A', 'AUTO-STD', 'Probe', 1000.005, DATE '2025-01-01')"),
      ("INSERT INTO commission_pay.policies (policy_id, policy_no, product_code, holder_name, annual_premium,"
      " issued_date) VALUES (902, 'PRB-5B', 'AUTO-STD', 'Probe', 1000.0049, DATE '2025-01-01')"),
      "SELECT annual_premium FROM commission_pay.policies WHERE policy_id IN (901, 902) ORDER BY policy_id"]),
    ("P6", None, "ROUND(x, 2) at the half cent: 2.345, 0.125, -2.345, 2.3449999",
     [("SELECT ROUND(2.345, 2), ROUND(0.125, 2), ROUND(-2.345, 2), ROUND(2.3449999, 2){dual}", None)]),
    ("P7", "D4", "commission at a half cent: premium 10003.00, rate 10, split 60 (exact 50.015)",
     [{"oracle": "SELECT ROUND(10003.00 / 12 * 10 / 100 * 60 / 100, 2) FROM dual",
       "pg": "SELECT commission_pay.commission_amount(10003.00, 10, 60)"}]),
    ("P7b", None, "the same with PostgreSQL's native numeric (what a naive port gives; not used)",
     [{"oracle": "SELECT ROUND(10003.00 / 12 * 10 / 100 * 60 / 100, 2) FROM dual",
       "pg": "SELECT ROUND(10003.00 / 12 * 10 / 100 * 60 / 100, 2)"}]),
    ("P8", "D5", "non-integer into an unconstrained NUMBER id column (rate_audit_log.agent_id = 1.5)",
     ["INSERT INTO commission_pay.rate_audit_log (action, agent_id, actor) VALUES ('PROBE', 1.5, 'probe')",
      "SELECT agent_id FROM commission_pay.rate_audit_log WHERE action = 'PROBE'"]),
]


def run_probe(conn, engine: str, statements) -> str:
    out = []
    try:
        for stmt in statements:
            param = None
            if isinstance(stmt, dict):
                stmt = stmt[engine]
            if isinstance(stmt, tuple):
                stmt, param = stmt
            if "{s}" in stmt:
                stmt = stmt.replace("{s}", ":1" if engine == "oracle" else "%s")
            stmt = stmt.replace("{dual}", " FROM dual" if engine == "oracle" else "")
            cur = conn.cursor()
            cur.execute(stmt, [param] if param is not None else [])
            if stmt.lstrip().upper().startswith("SELECT"):
                out.append(", ".join(", ".join(_fmt_plain(v) for v in r) for r in cur.fetchall()))
            cur.close()
        result = "accepted" + (f" -> {'; '.join(out)}" if out else "")
    except (oracledb.Error, psycopg.Error) as exc:  # the rejection itself is the outcome
        code = getattr(getattr(exc, "args", [None])[0], "full_code", None) or getattr(exc, "sqlstate", None)
        result = f"rejected ({code})" if code else f"rejected ({type(exc).__name__})"
    finally:
        conn.rollback()
    return result


def _fmt_plain(v) -> str:
    return format(Decimal(v).normalize(), "f") if isinstance(v, (int, Decimal)) else str(v)


def money(v) -> str:
    return f"{Decimal(v):,.2f}"


# --- schema translation -------------------------------------------------------

def expected_pg_type(data_type: str, precision, scale, char_length, name: str) -> str:
    if data_type == "VARCHAR2":
        return f"character varying({int(char_length)})"
    if data_type == "DATE":
        return "timestamp(0) without time zone"
    if data_type.startswith("TIMESTAMP("):
        return f"timestamp({data_type[10:-1]}) without time zone"
    if data_type == "NUMBER" and precision is not None:
        return f"numeric({int(precision)},{int(scale or 0)})"
    if data_type == "NUMBER":
        if name.endswith(("_id", "_key")) or name == "policy_rows":
            return "bigint"
        return "numeric"
    return f"?{data_type}"


def schema_rows(ora, pg, ora_pay) -> list[dict]:
    rows = []
    for schema, table, _pk, _sums in RELATIONS:
        o_cols = query(ora, """
            SELECT LOWER(c.column_name), c.data_type, c.data_precision, c.data_scale, c.char_length, c.nullable,
                   (SELECT COUNT(*) FROM all_tab_identity_cols i WHERE i.owner = c.owner
                       AND i.table_name = c.table_name AND i.column_name = c.column_name)
              FROM all_tab_columns c WHERE c.owner = :1 AND c.table_name = :2 ORDER BY c.column_id""",
                       [schema.upper(), table.upper()])
        p_cols = query(pg, """
            SELECT a.attname, format_type(a.atttypid, a.atttypmod), a.attnotnull, a.attidentity <> ''
              FROM pg_attribute a JOIN pg_class c ON c.oid = a.attrelid
              JOIN pg_namespace n ON n.oid = c.relnamespace
             WHERE n.nspname = %s AND c.relname = %s AND a.attnum > 0 AND NOT a.attisdropped
             ORDER BY a.attnum""", [schema, table])
        is_mv = table == RELATIONS[-1][1]
        problems = []
        if [c[0] for c in o_cols] != [c[0] for c in p_cols]:
            problems.append("column list differs")
        for o, p in zip(o_cols, p_cols):
            want = expected_pg_type(o[1], o[2], o[3], o[4], o[0])
            if p[1] != want:
                problems.append(f"{o[0]}: {p[1]} (expected {want})")
            if not is_mv and (o[5] == "N") != p[2]:
                problems.append(f"{o[0]}: nullability")
            if bool(o[6]) != p[3]:
                problems.append(f"{o[0]}: identity")
        o_ident = sum(1 for c in o_cols if c[6])
        if is_mv:
            o_meta = query(ora, "SELECT refresh_method, refresh_mode, build_mode FROM all_mviews"
                                " WHERE owner = :1 AND mview_name = :2", [schema.upper(), table.upper()])[0]
            p_meta = query(pg, "SELECT ispopulated FROM pg_matviews WHERE schemaname = %s AND matviewname = %s",
                           [schema, table])[0]
            src = f"MV, {len(o_cols)} columns, {'/'.join(o_meta)}"
            tgt = f"MV, {len(p_cols)} columns, {'populated' if p_meta[0] else 'NOT populated'}, complete refresh on demand"
            if not p_meta[0]:
                problems.append("MV not populated")
        else:
            o_cnt = query(ora, """
                SELECT (SELECT COUNT(*) FROM all_indexes WHERE table_owner = :o AND table_name = :t
                           AND uniqueness = 'UNIQUE'),
                       (SELECT COUNT(*) FROM all_constraints WHERE owner = :o AND table_name = :t
                           AND constraint_type = 'C'
                           AND NOT REGEXP_LIKE(search_condition_vc, '^"[A-Z0-9_$#]+" IS NOT NULL$')),
                       (SELECT COUNT(*) FROM all_constraints WHERE owner = :o AND table_name = :t
                           AND constraint_type = 'R') FROM dual""", {"o": schema.upper(), "t": table.upper()})[0]
            p_cnt = query(pg, """
                SELECT (SELECT COUNT(*) FROM pg_index WHERE indrelid = %(t)s::regclass AND indisunique),
                       (SELECT COUNT(*) FROM pg_constraint WHERE conrelid = %(t)s::regclass AND contype = 'c'
                           AND conname NOT LIKE '%%\\_nonempty'),
                       (SELECT COUNT(*) FROM pg_constraint WHERE conrelid = %(t)s::regclass AND contype = 'f'),
                       (SELECT COUNT(*) FROM pg_constraint WHERE conrelid = %(t)s::regclass AND contype = 'c'
                           AND conname LIKE '%%\\_nonempty')""",
                          {"t": f"{schema}.{table}"})[0]
            if tuple(int(x) for x in o_cnt) != tuple(int(x) for x in p_cnt[:3]):
                problems.append(f"unique/check/FK counts {tuple(o_cnt)} vs {tuple(p_cnt)}")
            src = f"{len(o_cols)} cols, {o_ident} identity, unique {o_cnt[0]}, check {o_cnt[1]}, FK {o_cnt[2]}"
            tgt = f"{len(p_cols)} cols, {sum(1 for c in p_cols if c[3])} identity, unique {p_cnt[0]}, " \
                  f"check {p_cnt[1]} (+{p_cnt[3]} non-empty, D3), FK {p_cnt[2]}"
        rows.append({"unit": f"{schema}.{table}", "source": src, "target": tgt,
                     "difference": "; ".join(problems) or "none", "verdict": RED if problems else OK})

    o_attrs = query(ora_pay, "SELECT LOWER(attr_name) || ' ' || attr_type_name FROM all_type_attrs"
                         " WHERE owner = 'COMMISSION_PAY' AND type_name = 'SPLIT_ALLOC_T' ORDER BY attr_no")
    p_attrs = query(pg, """
        SELECT a.attname || ' ' || format_type(a.atttypid, a.atttypmod) FROM pg_type t
          JOIN pg_namespace n ON n.oid = t.typnamespace JOIN pg_attribute a ON a.attrelid = t.typrelid
         WHERE n.nspname = 'commission_pay' AND t.typname = 'split_alloc_t' AND a.attnum > 0 ORDER BY a.attnum""")
    o_txt = ", ".join(r[0] for r in o_attrs)
    p_txt = ", ".join(r[0] for r in p_attrs)
    ok = [r[0].replace("NUMBER", "numeric") for r in o_attrs] == [r[0] for r in p_attrs] and bool(p_attrs)
    rows.append({"unit": "type commission_pay.split_alloc_t", "source": f"OBJECT ({o_txt})",
                 "target": f"composite ({p_txt})", "difference": "none" if ok else "attributes differ",
                 "verdict": OK if ok else RED})
    o_coll = query(ora_pay, "SELECT coll_type, elem_type_name FROM all_coll_types"
                        " WHERE owner = 'COMMISSION_PAY' AND type_name = 'SPLIT_ALLOC_TAB'")
    p_dom = query(pg, """
        SELECT format_type(t.typbasetype, t.typtypmod) FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace
         WHERE n.nspname = 'commission_pay' AND t.typname = 'split_alloc_tab' AND t.typtype = 'd'""")
    ok = bool(o_coll) and bool(p_dom) and o_coll[0] == ("TABLE", "SPLIT_ALLOC_T") \
        and p_dom[0][0].endswith("split_alloc_t[]")
    rows.append({"unit": "type commission_pay.split_alloc_tab",
                 "source": f"{o_coll[0][0]} OF {o_coll[0][1]}" if o_coll else "missing",
                 "target": f"domain over {p_dom[0][0]}" if p_dom else "missing",
                 "difference": "none" if ok else "collection type differs", "verdict": OK if ok else RED})
    return rows


# --- data ---------------------------------------------------------------------

def table_rows(ora, pg, o_m, p_m) -> list[dict]:
    rows = []
    for schema, table, pk, sums in RELATIONS:
        name = f"{schema}.{table}"
        cols = oracle_columns(ora, schema, table)
        o_rows = fetch_rows(ora, schema, table, cols, pk)
        p_rows = fetch_rows(pg, schema, table, cols, pk)
        only_o = sorted(set(o_rows) - set(p_rows))
        only_p = sorted(set(p_rows) - set(o_rows))
        changed = sorted(k for k in set(o_rows) & set(p_rows) if o_rows[k] != p_rows[k])
        o_t, p_t = o_m["tables"][name], p_m["tables"][name]

        def fig(t):
            return "; ".join([f"rows {t['rows']}"] + [
                f"Σ{c} {money(v) if c != 'policy_rows' else v}" for c, v in t["sums"].items()])

        diffs = [f"rows {p_t['rows'] - o_t['rows']:+d}"] + [
            f"Σ{c} {Decimal(p_t['sums'][c]) - Decimal(v):+,.2f}" for c, v in o_t["sums"].items()]
        row_cmp = f"{len(o_rows) - len(only_o) - len(changed)}/{len(o_rows)} rows identical, all {len(cols)} columns"
        problems = []
        if only_o:
            problems.append(f"{len(only_o)} missing in PG (e.g. {only_o[0]})")
        if only_p:
            problems.append(f"{len(only_p)} extra in PG (e.g. {only_p[0]})")
        if changed:
            k = changed[0]
            col = next(c for c, a, b in zip(cols, o_rows[k], p_rows[k]) if a != b)
            problems.append(f"{len(changed)} rows differ (e.g. key {k} column {col})")
        same_figs = o_t == p_t
        if not same_figs:
            problems.append("control figures differ")
        rows.append({"unit": name, "source": fig(o_t), "target": fig(p_t),
                     "difference": ", ".join(diffs), "row_compare": row_cmp + ("; " + "; ".join(problems) if problems else ""),
                     "verdict": RED if problems else OK, "o_rows": o_t["rows"], "p_rows": p_t["rows"]})
    return rows


def grouped_rows(o_g: dict, p_g: dict, field: str = "commission_amt") -> list[dict]:
    rows = []
    for key in sorted(set(o_g) | set(p_g)):
        o, p = o_g.get(key), p_g.get(key)
        ov = Decimal(o[field]) if o else None
        pv = Decimal(p[field]) if p else None
        ok = o is not None and p is not None and o == p
        rows.append({"unit": key,
                     "source": f"{money(ov)} ({o['rows'] if 'rows' in o else o['policy_rows']} rows)" if o else "absent",
                     "target": f"{money(pv)} ({p['rows'] if 'rows' in p else p['policy_rows']} rows)" if p else "absent",
                     "difference": f"{(pv or 0) - (ov or 0):+,.2f}", "verdict": OK if ok else RED,
                     "o": ov, "p": pv})
    return rows


def golden_rows(o_m: dict) -> list[dict]:
    golden = json.loads(GOLDEN.read_text())
    rows = []
    for section in ("tables", "ledger_by_agent", "ledger_by_period", "ledger_by_agent_period",
                    "mv_rows", "ledger_recompute"):
        g, o = golden[section], o_m[section]
        bad = sorted(k for k in set(g) | set(o) if g.get(k) != o.get(k))
        rows.append({"unit": section, "source": f"pinned: {len(g)} entries", "target": f"live Oracle: {len(o)} entries",
                     "difference": "none" if not bad else f"{len(bad)} differ (e.g. {bad[0]})",
                     "verdict": OK if not bad else RED})
    return rows


def recompute_rows(o_m: dict, p_m: dict) -> list[dict]:
    o, p = o_m["ledger_recompute"], p_m["ledger_recompute"]
    rows = []
    for key, label in [("stored_total", "stored commission_amt total"),
                       ("rounded_total", "Σ ROUND(premium/12 × rate/100 × split/100, 2), in-engine"),
                       ("unrounded_total", "Σ unrounded formula, in-engine"),
                       ("rows_not_matching_round", "ledger rows where in-engine ROUND ≠ stored amount")]:
        ov, pv = o[key], p[key]
        is_count = key == "rows_not_matching_round"
        ok = Decimal(ov) == Decimal(pv) and (not is_count or int(ov) == 0)
        rows.append({"unit": label, "source": str(ov) if is_count else money(ov),
                     "target": str(pv) if is_count else money(pv),
                     "difference": f"{int(pv) - int(ov):+d}" if is_count else f"{Decimal(pv) - Decimal(ov):+,.2f}",
                     "verdict": OK if ok else RED})
    return rows


def probe_rows() -> list[dict]:
    rows = []
    with oracle_connect("commission_pay") as ora, pg_connect("commission_pay") as pg:
        for pid, decision, what, statements in PROBES:
            o = run_probe(ora, "oracle", statements)
            p = run_probe(pg, "pg", statements)
            if pid == "P7b":
                rows.append({"unit": f"{pid} {what}", "source": o, "target": p,
                             "difference": "same outcome" if o == p else "outcome differs", "verdict": INFO})
                continue
            same = o.split(" (")[0] == p.split(" (")[0] if o.startswith("rejected") else o == p
            if same:
                verdict = OK
            elif decision and decision in DECISIONS:
                verdict = f"{ACCEPTED} ({decision}: {DECISIONS[decision]})"
            else:
                verdict = f"{RED} (decision {decision or 'needed'} pending)"
            rows.append({"unit": f"{pid} {what}", "source": o, "target": p,
                         "difference": "same outcome" if same else "outcome differs", "verdict": verdict})
    return rows


# --- half-cent rounding (decision D4) -----------------------------------------

GRID_RATES = ["8", "8.5", "8.75", "9.5", "10", "15", "12.25", "7.33"]
GRID_SPLITS = ["20", "30", "35", "40", "50", "60", "65", "100", "33.33", "12.5"]
GRID_CENTS = (1_000_000, 1_020_000)  # premiums 10,000.00 to 10,200.00 in steps of one cent

# COMMISSION_PKG's own arithmetic: PL/SQL NUMBER variables, the package's expression.
ORACLE_GRID = """WITH FUNCTION pkg_amt(p NUMBER, r NUMBER, s NUMBER) RETURN NUMBER IS
    BEGIN RETURN ROUND(p / 12 * r / 100 * s / 100, 2); END;
SELECT pc, r, s, pkg_amt(pc / 100, r, s) FROM
  (SELECT {lo} - 1 + LEVEL AS pc FROM dual CONNECT BY LEVEL <= {n}),
  (SELECT TO_NUMBER(COLUMN_VALUE) r FROM TABLE(sys.odcivarchar2list({rates}))),
  (SELECT TO_NUMBER(COLUMN_VALUE) s FROM TABLE(sys.odcivarchar2list({splits})))"""
PG_GRID = """SELECT pc, r, s, commission_pay.commission_amount(pc / 100.0, r, s),
       ROUND(pc / 100.0 / 12 * r / 100 * s / 100, 2), ROUND(pc * r * s / 12000000.0, 2)
  FROM generate_series({lo}, {hi}) pc,
       unnest(ARRAY[{rates}]::numeric[]) r, unnest(ARRAY[{splits}]::numeric[]) s"""


def grid_rows(ora, pg) -> list[dict]:
    lo, hi = GRID_CENTS
    lits = {"rates": ",".join(f"'{x}'" for x in GRID_RATES),
            "splits": ",".join(f"'{x}'" for x in GRID_SPLITS)}

    def key(pc, r, s):
        return int(pc), Decimal(r).normalize(), Decimal(s).normalize()

    ora_amt = {key(pc, r, s): Decimal(a) for pc, r, s, a in
               query(ora, ORACLE_GRID.format(lo=lo, n=hi - lo + 1, **lits))}
    pg_rows = {key(pc, r, s): tuple(Decimal(x) for x in v) for pc, r, s, *v in
               query(pg, PG_GRID.format(lo=lo, hi=hi, **lits))}
    n = len(ora_amt)
    missing = len(set(ora_amt) ^ set(pg_rows))
    spec = (f"{n:,} combinations: premium {lo / 100:,.2f} to {hi / 100:,.2f} by 0.01 x "
            f"{len(GRID_RATES)} rates x {len(GRID_SPLITS)} splits")

    def compare(i):
        diff = [k for k in ora_amt if k in pg_rows and pg_rows[k][i] != ora_amt[k]]
        ex = ""
        if diff:
            pc, r, s = min(diff)
            ex = f" (e.g. premium {pc / 100:,.2f} rate {r:f} split {s:f}: Oracle {ora_amt[min(diff)]}, " \
                 f"PG {pg_rows[min(diff)][i]})"
        return len(diff), ex

    d_a, ex_a = compare(0)
    d_n, ex_n = compare(1)
    d_b, ex_b = compare(2)
    ledger = query(pg, f"""
        SELECT COUNT(*), COUNT(*) FILTER (WHERE commission_pay.commission_amount(l.base_premium, r.rate_pct,
                                                l.split_pct) = l.commission_amt)
          FROM {LEDGER} l JOIN {RATES} r ON r.rate_id = l.rate_id""")[0]
    return [
        {"unit": "D4 A: PG commission_amount vs Oracle COMMISSION_PKG arithmetic (must be 0)",
         "source": spec, "target": f"{n - d_a - missing:,} identical", "difference": f"{d_a + missing} differ{ex_a}",
         "verdict": OK if d_a + missing == 0 else RED},
        {"unit": "PG commission_amount on every stored ledger row", "source": f"{ledger[0]} stored amounts",
         "target": f"{ledger[1]} recomputed equal", "difference": f"{ledger[0] - ledger[1]} differ",
         "verdict": OK if ledger[0] == ledger[1] and ledger[0] > 0 else RED},
        {"unit": "Not used: PG native numeric ROUND(premium / 12 * rate / 100 * split / 100, 2)",
         "source": spec, "target": f"{n - d_n:,} identical", "difference": f"{d_n} differ by one cent{ex_n}",
         "verdict": INFO},
        {"unit": "Not chosen, option B: exact ROUND(premium x rate x split / 120000, 2), half up",
         "source": spec, "target": f"{n - d_b:,} identical", "difference": f"{d_b} differ by one cent{ex_b}",
         "verdict": INFO},
    ]


# --- report -------------------------------------------------------------------

def md_table(rows, cols, headers) -> list[str]:
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    for r in rows:
        out.append("| " + " | ".join(str(r[c]).replace("|", "\\|") for c in cols) + " |")
    return out


def verdict_cell(v: str) -> str:
    return f"**{v}**" if v.startswith(RED) else v


def total_row(rows, label="**Total**") -> dict:
    o = sum(r["o"] for r in rows if r["o"] is not None)
    p = sum(r["p"] for r in rows if r["p"] is not None)
    red = sum(1 for r in rows if r["verdict"].startswith(RED))
    return {"unit": label, "source": f"**{money(o)}**", "target": f"**{money(p)}**",
            "difference": f"**{p - o:+,.2f}**", "verdict": f"**{len(rows) - red}/{len(rows)} MATCH**"}


def main() -> int:
    with oracle_connect() as ora, pg_connect() as pg:
        o_m, p_m = control_metrics(ora), control_metrics(pg)
        tables = table_rows(ora, pg, o_m, p_m)
        rounding = grid_rows(ora, pg)
        with oracle_connect("commission_pay") as ora_pay:
            schema = schema_rows(ora, pg, ora_pay)
    probes = probe_rows()
    agents = grouped_rows(o_m["ledger_by_agent"], p_m["ledger_by_agent"])
    periods = grouped_rows(o_m["ledger_by_period"], p_m["ledger_by_period"])
    agent_periods = grouped_rows(o_m["ledger_by_agent_period"], p_m["ledger_by_agent_period"])
    mv = grouped_rows(o_m["mv_rows"], p_m["mv_rows"], "total_commission")
    golden = golden_rows(o_m)
    recompute = recompute_rows(o_m, p_m)

    sections = [tables, schema, probes, agents, periods, agent_periods, mv, golden, recompute, rounding]
    red = sum(1 for s in sections for r in s if str(r["verdict"]).startswith(RED))

    for r in tables + schema + probes + golden + recompute + rounding:
        r["verdict"] = verdict_cell(r["verdict"])
    t_red = sum(1 for r in tables if r["verdict"].startswith("**"))
    tables_total = {"unit": "**Total (13 relations)**",
                    "source": f"**{sum(r['o_rows'] for r in tables)} rows**",
                    "target": f"**{sum(r['p_rows'] for r in tables)} rows**",
                    "difference": f"**{sum(r['p_rows'] - r['o_rows'] for r in tables):+d} rows**",
                    "row_compare": "", "verdict": f"**{len(tables) - t_red}/{len(tables)} MATCH**"}
    std = ["unit", "source", "target", "difference", "verdict"]
    hdr = ["Oracle Free", "PostgreSQL 16", "Difference", "Verdict"]
    md = ["## Reconciliation: Commission Pay, Oracle → PostgreSQL 16", "",
          f"Overall: **{'ALL MATCH' if red == 0 else f'{red} RED ROW(S)'}**", "",
          "### Tables (one row per table; every row compared on its key and every column)", ""]
    md += md_table(tables + [tables_total], ["unit", "source", "target", "difference", "row_compare", "verdict"],
                   ["Table", *hdr[:3], "Row-level compare", "Verdict"])
    md += ["", "### Commission ledger per agent (to the cent)", ""]
    md += md_table(agents + [total_row(agents)], std, ["Agent", *hdr])
    md += ["", "### Commission ledger per period (to the cent)", ""]
    md += md_table(periods + [total_row(periods)], std, ["Period", *hdr])
    md += ["", "### MV_AGENT_COMMISSION_SUMMARY totals", ""]
    mv_total = total_row(mv, "**All MV rows**")
    md += md_table([mv_total], std, ["MV", *hdr])
    md += ["", "<details><summary>MV per row (agent, period, line of business)</summary>", ""]
    md += md_table(mv, std, ["Agent period LOB", *hdr]) + ["", "</details>", ""]
    md += ["<details><summary>Ledger per agent and period</summary>", ""]
    md += md_table(agent_periods + [total_row(agent_periods)], std, ["Agent period", *hdr]) + ["", "</details>", ""]
    md += ["### Ledger recomputed from premium, rate and split", ""]
    md += md_table(recompute, std, ["Check", *hdr])
    md += ["", "### Half-cent rounding (decision D4)", ""]
    md += md_table(rounding, std, ["Check", *hdr])
    md += ["", "### Schema translation", ""]
    md += md_table(schema, std, ["Object", *hdr])
    md += ["", "### Constraint and rounding behaviour (probes, rolled back)", ""]
    md += md_table(probes, std, ["Probe", *hdr])
    md += ["", "### Live Oracle vs pinned baseline (golden/oracle_baseline.json)", ""]
    md += md_table(golden, std, ["Section", "Pinned", "Live", "Difference", "Verdict"])
    md.append("")

    REPORTS.mkdir(exist_ok=True)
    (REPORTS / "reconciliation.md").write_text("\n".join(md))
    (REPORTS / "reconciliation.json").write_text(json.dumps(
        {"red_rows": red, "oracle": o_m, "postgres": p_m}, indent=2, sort_keys=True) + "\n")
    print("\n".join(md))
    print(f"\nRECONCILIATION: {'ALL MATCH' if red == 0 else f'{red} RED ROW(S)'}")
    return 0 if red == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
