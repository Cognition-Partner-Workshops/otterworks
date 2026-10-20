"""Drive COMMISSION_PKG through SQL and record what it does.

Every call goes through an anonymous PL/SQL block on the ``caller`` session.
Before and after each call the four tables the package writes are read from
a separate ``observer`` session, so a recorded write is one that was
committed. The result of a call is an :class:`Outcome`: the inputs, the OUT
values or the exact ORA code and message, and the per-table row diff.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any

import oracledb

oracledb.defaults.fetch_decimals = True

HERE = Path(__file__).resolve().parent
SEED_SQL = HERE.parent / "db" / "oltp" / "02_seed.sql"

# Tables the package writes, with their primary key. Volatile columns
# (server timestamps) are excluded from every snapshot.
WRITTEN_TABLES: dict[str, str] = {
    "commission_rates": "rate_id",
    "commission_splits": "split_id",
    "commission_ledger": "ledger_id",
    "rate_audit_log": "audit_id",
}
VOLATILE_COLUMNS = {"created_at", "logged_at", "calculated_at"}

# Identity columns that the seed does not realign itself; they restart at 1
# on every reset so recorded ids are deterministic.
RESTART_IDENTITIES = {
    "commission_splits": "split_id",
    "commission_ledger": "ledger_id",
    "rate_audit_log": "audit_id",
}
RESET_DELETE_ORDER = [
    "commission_ledger",
    "commission_splits",
    "rate_audit_log",
    "commission_rates",
    "policies",
    "agents",
    "products",
]

ORA_LINE = re.compile(r"^(ORA-\d{5}): (.*)$")

SQL = {
    "upsert_commission_rate": (
        "BEGIN commission_pkg.upsert_commission_rate("
        ":p_product_code, :p_agent_id, :p_rate_pct, :p_effective_from, :p_actor, :o_rate_id); END;"
    ),
    "end_commission_rate": (
        "BEGIN commission_pkg.end_commission_rate("
        ":p_product_code, :p_agent_id, :p_effective_to, :p_actor); END;"
    ),
    "set_commission_splits": (
        "BEGIN commission_pkg.set_commission_splits(:p_policy_id, :p_splits, :p_actor); END;"
    ),
    "resolve_rate": (
        "BEGIN :rate_id := commission_pkg.resolve_rate(:p_product_code, :p_agent_id, :p_as_of); END;"
    ),
    "calculate_policy_commission": (
        "BEGIN commission_pkg.calculate_policy_commission(:p_policy_id, :p_period_month, :p_actor); END;"
    ),
}


def connect_params() -> dict[str, str]:
    return {
        "user": os.environ.get("INSURANCE_DB_USER", "commission_pay"),
        "password": os.environ.get("INSURANCE_DB_PASSWORD", "commission_pay"),
        "dsn": os.environ.get(
            "INSURANCE_DSN",
            f"localhost:{os.environ.get('INSURANCE_DB_PORT', '51521')}/FREEPDB1",
        ),
    }


def connect() -> oracledb.Connection:
    conn = oracledb.connect(**connect_params())
    conn.autocommit = False
    return conn


# --------------------------------------------------------------------------
# Value normalisation: everything recorded is JSON with exact decimals.
# --------------------------------------------------------------------------


def norm(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, dt.datetime):
        if value.time() == dt.time(0):
            return value.date().isoformat()
        return value.isoformat()
    if isinstance(value, dt.date):
        return value.isoformat()
    if isinstance(value, list | tuple):
        return [norm(v) for v in value]
    if isinstance(value, dict):
        return {k: norm_column(k, v) for k, v in value.items()}
    return value


def norm_column(column: str, value: Any) -> Any:
    # Surrogate keys are integers; every other NUMBER is recorded as an exact decimal string.
    if column.endswith("_id") and isinstance(value, Decimal) and value == value.to_integral_value():
        return int(value)
    return norm(value)


def to_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    return value if isinstance(value, Decimal) else Decimal(str(value))


# --------------------------------------------------------------------------
# Snapshots and diffs
# --------------------------------------------------------------------------


def snapshot(conn: oracledb.Connection) -> dict[str, dict[Any, dict[str, Any]]]:
    snap: dict[str, dict[Any, dict[str, Any]]] = {}
    with conn.cursor() as cur:
        for table, pk in WRITTEN_TABLES.items():
            cur.execute(f"SELECT * FROM {table} ORDER BY {pk}")
            cols = [d[0].lower() for d in cur.description]
            rows = {}
            for raw in cur.fetchall():
                row = {c: norm_column(c, v) for c, v in zip(cols, raw, strict=True) if c not in VOLATILE_COLUMNS}
                rows[row[pk]] = row
            snap[table] = rows
    # The observer must not hold a read-consistent view across calls.
    conn.rollback()
    return snap


def diff(before: dict, after: dict) -> dict[str, dict[str, list]]:
    writes: dict[str, dict[str, list]] = {}
    for table, pk in WRITTEN_TABLES.items():
        b, a = before[table], after[table]
        inserted = [a[k] for k in sorted(a.keys() - b.keys())]
        deleted = [b[k] for k in sorted(b.keys() - a.keys())]
        updated = []
        for k in sorted(a.keys() & b.keys()):
            if a[k] != b[k]:
                changes = {c: [b[k][c], a[k][c]] for c in a[k] if a[k][c] != b[k][c]}
                updated.append({pk: k, "changes": changes})
        entry = {
            name: rows
            for name, rows in (("inserted", inserted), ("updated", updated), ("deleted", deleted))
            if rows
        }
        if entry:
            writes[table] = entry
    return writes


# --------------------------------------------------------------------------
# Outcome of a call
# --------------------------------------------------------------------------


@dataclass
class OraError:
    code: str
    message: str

    @classmethod
    def from_exception(cls, exc: oracledb.DatabaseError) -> OraError:
        (err,) = exc.args
        first = str(err.message).splitlines()[0]
        m = ORA_LINE.match(first)
        if not m:
            return cls(code=getattr(err, "full_code", "") or "UNKNOWN", message=first)
        return cls(code=m.group(1), message=m.group(2))


@dataclass
class Outcome:
    call: str
    inputs: dict[str, Any]
    outputs: dict[str, Any] = field(default_factory=dict)
    error: OraError | None = None
    writes: dict[str, dict[str, list]] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.error is None

    def rows(self, table: str, kind: str = "inserted") -> list[dict[str, Any]]:
        return self.writes.get(table, {}).get(kind, [])

    def assert_ok(self) -> Outcome:
        assert self.error is None, f"{self.call} raised {self.error.code}: {self.error.message}"
        return self

    def assert_error(self, code: str, message: str) -> Outcome:
        assert self.error is not None, f"{self.call} succeeded, expected {code}"
        assert (self.error.code, self.error.message) == (code, message)
        return self

    def assert_no_writes(self) -> Outcome:
        assert self.writes == {}, f"{self.call} left committed writes: {self.writes}"
        return self

    def record(self) -> dict[str, Any]:
        rec: dict[str, Any] = {"call": self.call, "inputs": norm(self.inputs)}
        if self.call in SQL:
            rec["sql"] = SQL[self.call]
        if self.error is None:
            rec["outputs"] = norm(self.outputs)
        else:
            rec["error"] = {"code": self.error.code, "message": self.error.message}
        rec["writes"] = self.writes
        return rec


# --------------------------------------------------------------------------
# The harness
# --------------------------------------------------------------------------


def seed_statements() -> list[str]:
    lines = []
    for line in SEED_SQL.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("--"):
            continue
        if stripped.upper().startswith(("WHENEVER", "EXIT", "COMMIT")):
            continue
        lines.append(line)
    return [s.strip() for s in "\n".join(lines).split(";") if s.strip()]


def reset_to_seed(conn: oracledb.Connection) -> None:
    """Put COMMISSION_PAY back to exactly the state 02_seed.sql produces."""
    with conn.cursor() as cur:
        for table in RESET_DELETE_ORDER:
            cur.execute(f"DELETE FROM {table}")
        conn.commit()
        for table, col in RESTART_IDENTITIES.items():
            cur.execute(
                f"ALTER TABLE {table} MODIFY {col} GENERATED BY DEFAULT ON NULL AS IDENTITY (START WITH 1)"
            )
        for stmt in seed_statements():
            cur.execute(stmt)
    conn.commit()


class Harness:
    def __init__(self, caller: oracledb.Connection, observer: oracledb.Connection):
        self.caller = caller
        self.observer = observer
        self.steps: list[dict[str, Any]] = []
        self._split_tab = caller.gettype("SPLIT_ALLOC_TAB")
        self._split_t = caller.gettype("SPLIT_ALLOC_T")

    # -- recording ---------------------------------------------------------

    def _run(self, call: str, sql: str, binds: dict[str, Any], inputs: dict[str, Any],
             out_names: tuple[str, ...] = ()) -> Outcome:
        before = snapshot(self.observer)
        outcome = Outcome(call=call, inputs=inputs)
        with self.caller.cursor() as cur:
            try:
                cur.execute(sql, binds)
                outcome.outputs = {n: binds[n].getvalue() for n in out_names}
            except oracledb.DatabaseError as exc:
                outcome.error = OraError.from_exception(exc)
        outcome.writes = diff(before, snapshot(self.observer))
        self.steps.append(outcome.record())
        return outcome

    def setup(self, sql: str, params: dict[str, Any] | None = None, note: str = "") -> Outcome:
        """Direct fixture setup outside the package, committed and recorded."""
        before = snapshot(self.observer)
        with self.caller.cursor() as cur:
            cur.execute(sql, params or {})
        self.caller.commit()
        outcome = Outcome(call="setup", inputs={"sql": sql, "params": params or {}, "note": note})
        outcome.writes = diff(before, snapshot(self.observer))
        self.steps.append(outcome.record())
        return outcome

    def note(self, label: str, value: Any) -> None:
        """Record an observation (e.g. a read-back) alongside the calls."""
        self.steps.append({"observe": label, "value": norm(value)})

    # -- the five procedures ----------------------------------------------

    def upsert_commission_rate(self, product_code, agent_id, rate_pct, effective_from, actor) -> Outcome:
        with self.caller.cursor() as cur:
            o_rate_id = cur.var(oracledb.DB_TYPE_NUMBER)
        inputs = {
            "p_product_code": product_code,
            "p_agent_id": agent_id,
            "p_rate_pct": to_decimal(rate_pct),
            "p_effective_from": effective_from,
            "p_actor": actor,
        }
        return self._run("upsert_commission_rate", SQL["upsert_commission_rate"],
                         {**inputs, "o_rate_id": o_rate_id}, inputs, ("o_rate_id",))

    def end_commission_rate(self, product_code, agent_id, effective_to, actor) -> Outcome:
        inputs = {
            "p_product_code": product_code,
            "p_agent_id": agent_id,
            "p_effective_to": effective_to,
            "p_actor": actor,
        }
        return self._run("end_commission_rate", SQL["end_commission_rate"], dict(inputs), inputs)

    def set_commission_splits(self, policy_id, splits, actor) -> Outcome:
        """``splits`` is a list of (agent_id, split_pct) or None for a NULL collection."""
        with self.caller.cursor() as cur:
            var = cur.var(self._split_tab)
        if splits is None:
            var.setvalue(0, None)
        else:
            tab = self._split_tab.newobject()
            for agent_id, pct in splits:
                item = self._split_t.newobject()
                item.AGENT_ID = agent_id
                item.SPLIT_PCT = to_decimal(pct)
                tab.append(item)
            var.setvalue(0, tab)
        inputs = {
            "p_policy_id": policy_id,
            "p_splits": None if splits is None
            else [{"agent_id": a, "split_pct": to_decimal(p)} for a, p in splits],
            "p_actor": actor,
        }
        binds = {"p_policy_id": policy_id, "p_splits": var, "p_actor": actor}
        return self._run("set_commission_splits", SQL["set_commission_splits"], binds, inputs)

    def resolve_rate(self, product_code, agent_id, as_of) -> Outcome:
        with self.caller.cursor() as cur:
            rate_id = cur.var(oracledb.DB_TYPE_NUMBER)
        inputs = {"p_product_code": product_code, "p_agent_id": agent_id, "p_as_of": as_of}
        return self._run("resolve_rate", SQL["resolve_rate"], {**inputs, "rate_id": rate_id},
                         inputs, ("rate_id",))

    def calculate_policy_commission(self, policy_id, period_month, actor) -> Outcome:
        inputs = {"p_policy_id": policy_id, "p_period_month": period_month, "p_actor": actor}
        return self._run("calculate_policy_commission", SQL["calculate_policy_commission"],
                         dict(inputs), inputs)

    # -- read-backs (not recorded unless passed to note()) ----------------

    def query(self, sql: str, params: dict[str, Any] | None = None, conn=None) -> list[dict[str, Any]]:
        conn = conn or self.observer
        with conn.cursor() as cur:
            cur.execute(sql, params or {})
            cols = [d[0].lower() for d in cur.description]
            rows = [dict(zip(cols, r, strict=True)) for r in cur.fetchall()]
        if conn is self.observer:
            conn.rollback()
        return rows

    def scalar(self, sql: str, params: dict[str, Any] | None = None, conn=None) -> Any:
        rows = self.query(sql, params, conn)
        assert len(rows) == 1, rows
        (value,) = rows[0].values()
        return value

    def rate(self, rate_id: int) -> dict[str, Any]:
        (row,) = self.query(
            "SELECT rate_id, product_code, agent_id, rate_pct, effective_from, effective_to, created_by"
            " FROM commission_rates WHERE rate_id = :id", {"id": rate_id})
        return norm(row)

    def ledger(self, policy_id: int, period_month: str) -> list[dict[str, Any]]:
        return norm(self.query(
            "SELECT ledger_id, agent_id, rate_id, split_pct, base_premium, commission_amt"
            " FROM commission_ledger WHERE policy_id = :p AND period_month = :m ORDER BY ledger_id",
            {"p": policy_id, "m": period_month}))

    def splits(self, policy_id: int) -> list[dict[str, Any]]:
        return norm(self.query(
            "SELECT split_id, agent_id, split_pct FROM commission_splits WHERE policy_id = :p"
            " ORDER BY split_id", {"p": policy_id}))


def dump_json(data: Any) -> str:
    return json.dumps(data, indent=2, sort_keys=True) + "\n"
