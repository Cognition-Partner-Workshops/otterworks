"""Spec-driven Oracle -> MongoDB loader library.

Generic over `.migration/03_mapping_spec.json`: reads each mapped collection's
root rows (optionally `root_where`) and its embeds' child rows (joined by
`parent_key`, optionally `child_where`), builds documents field-by-field from
the spec's `target` / `bson_type` / `rules`, and upserts by `_id`. Target writes
never leave the collections named on the call.

Conversions follow the Oracle source profile (skills/mongo-migration/profiles/
oracle.md) so loaded values canonicalize equal to the source under
recon/canon.py:

- CHAR/VARCHAR2: trailing spaces stripped; Oracle '' (read back as NULL) or a
  NULL with `empty_string_is_null` -> field omitted.
- `yn_to_bool` / bson_type "bool": Y/N-style flags -> bool.
- NUMBER(p,0) -> int; NUMBER(p,s) s>0 or bare NUMBER -> bson Decimal128
  quantized to the declared scale (spec decimal_round alias or column scale).
- DATE/TIMESTAMP -> naive datetime (UTC); `date_string_to_date*` rules on a
  VARCHAR2 parse per-field `date_format` (default %d-%b-%y); an unparseable
  text date -> field omitted and the row is quarantined to a JSONL file under
  migration/mongo/quarantine/ (never to the target db).
- `csv_to_array` rules or bson_type "array" on a string column -> list split
  on ',' with empty items dropped.
- UUID-ish strings are written as strings (uuid_normalize canonicalizes).

Key: `_id` is the single key column's value, or a subdocument keyed by
`key.target` names for a composite key; composite key columns are also
materialised as top-level fields (the harness keys documents on
`key.target` paths).

Idempotency: every row is `replace_one({_id}, upsert=True)`; after the load the
target's docs whose `_id` is absent from the source key set are deleted, so a
rerun converges to zero diff.
"""

from __future__ import annotations

import datetime as dt
import decimal
import json
import re
from pathlib import Path
from typing import Any

from bson.decimal128 import Decimal128

QUARANTINE_DIR = Path(__file__).resolve().parents[1] / "quarantine"

_NUM_RE = re.compile(r"NUMBER\s*\(\s*(\d+)\s*(?:,\s*(\d+))?\s*\)|NUMBER", re.I)


def _number_scale(source_type: str) -> tuple[int | None, int | None]:
    m = _NUM_RE.search(source_type or "")
    if not m:
        return None, None
    prec = int(m.group(1)) if m.group(1) else None
    scale = int(m.group(2)) if m.group(2) else 0 if m.group(1) else None
    return prec, scale


def _declared_scale(rules: list[str]) -> int | None:
    for name in rules or []:
        m = re.match(r"decimal_round:s(\d+)$", name)
        if m:
            return int(m.group(1))
    return None


def _has_rule(rules: list[str], base: str) -> bool:
    return any(r == base or r.startswith(base + ":") for r in rules or [])


def _to_decimal128(value: Any, places: int | None) -> Decimal128:
    d = value if isinstance(value, decimal.Decimal) else decimal.Decimal(str(value))
    if places is not None:
        d = d.quantize(decimal.Decimal(1).scaleb(-places), rounding=decimal.ROUND_HALF_EVEN)
    return Decimal128(d)


def _to_utc_naive(value: Any) -> dt.datetime:
    if isinstance(value, dt.datetime):
        v = value
    elif isinstance(value, dt.date):
        v = dt.datetime(value.year, value.month, value.day)
    else:
        raise ValueError(f"not a datetime: {value!r}")
    if v.tzinfo is not None:
        v = v.astimezone(dt.timezone.utc).replace(tzinfo=None)
    return v


def _parse_text_date(value: str, fmt: str) -> dt.datetime | None:
    try:
        return dt.datetime.strptime(value.strip(), fmt)
    except ValueError:
        return None


def _convert_value(field: dict, value: Any) -> tuple[Any, str | None]:
    """(mongo value, quarantine reason or None). Missing sentinel is None on
    a field we should omit; callers check `reason` first."""
    if value is None:
        return _OMIT, None
    rules = field.get("rules", [])
    bson_type = field.get("bson_type", "string")
    source_type = field.get("source_type", "") or ""
    if isinstance(value, str):
        if source_type.upper().startswith("CHAR") or _has_rule(rules, "rstrip_spaces"):
            value = value.rstrip(" ")
        if value == "" and _has_rule(rules, "empty_string_is_null"):
            return _OMIT, None
    if bson_type == "bool" or _has_rule(rules, "yn_to_bool") or _has_rule(rules, "int_to_bool"):
        if isinstance(value, str):
            token = value.strip().upper()
            if token in ("Y", "T", "1", "TRUE", "YES"):
                return True, None
            if token in ("N", "F", "0", "FALSE", "NO"):
                return False, None
            return value, None
        if isinstance(value, (int,)) and value in (0, 1):
            return bool(value), None
        return value, None
    if _has_rule(rules, "date_string_to_date") or (bson_type == "date" and isinstance(value, str)):
        fmt = field.get("date_format") or "%d-%b-%y"
        parsed = _parse_text_date(value, fmt)
        if parsed is None:
            return _OMIT, f"unparseable date {value!r}"
        return parsed, None
    if bson_type == "date":
        return _to_utc_naive(value), None
    if _has_rule(rules, "csv_to_array") or (bson_type == "array" and isinstance(value, str)):
        if not isinstance(value, str):
            return value, None
        if _csv_malformed(value):
            return _OMIT, "malformed csv"
        return [p.strip() for p in value.split(",") if p.strip() != ""], None
    if bson_type in ("long", "int"):
        return int(decimal.Decimal(str(value))), None
    if bson_type == "decimal":
        places = _declared_scale(rules)
        if places is None:
            _, scale = _number_scale(source_type)
            places = scale if (scale or 0) > 0 else 10
        return _to_decimal128(value, places), None
    if bson_type == "double":
        return float(value), None
    if bson_type == "binData":
        return bytes(value) if not isinstance(value, (bytes, bytearray)) else bytes(value), None
    if bson_type in ("object", "list") and isinstance(value, str):
        try:
            return json.loads(value), None
        except ValueError:
            return value, f"malformed json {value!r}"
    return value, None


def _csv_malformed(value: str) -> bool:
    """Malformed list grammar (D-decision: malformed lists quarantine):
    any quote char, a newline, a ';'/'|' delimiter, or an empty item between
    delimiters ('a,,b'). Leading/trailing empties are dropped, not malformed."""
    if any(ch in value for ch in ('"', "'", "\n", "\r", ";", "|")):
        return True
    parts = value.split(",")
    return any(p.strip() == "" for p in parts[1:-1])


def require_local_oracle_dsn(dsn: str) -> None:
    """Offline mode: the Oracle easy-connect DSN must be local. Host is the
    text before the first ':' or '/'; a '(' in the string means a TNS
    descriptor, which is refused outright."""
    if "(" in dsn:
        raise ValueError("offline mode refuses TNS descriptors in the Oracle DSN")
    host = dsn.split(":", 1)[0].split("/", 1)[0]
    if host not in ("127.0.0.1", "localhost"):
        raise ValueError(f"offline mode refuses non-local Oracle host {host!r}")


def require_local_uri(uri: str) -> None:
    """Offline mode: every node in the Mongo URI must be exactly 127.0.0.1 or
    localhost. Anything else (suffix matches like localhost.evil.example
    included) refuses the run."""
    from pymongo.uri_parser import parse_uri
    nodes = parse_uri(uri)["nodelist"]
    if not nodes:
        raise ValueError(f"no nodes in Mongo URI")
    for host, _port in nodes:
        if host not in ("127.0.0.1", "localhost"):
            raise ValueError(f"offline mode refuses non-local Mongo host {host!r}")


class _Omit:
    pass


_OMIT = _Omit()


def _apply_fields(row: dict[str, Any], field_specs: list[dict],
                  doc: dict, quarantine: list[dict], key_cols: set[str]) -> dict:
    for f in field_specs:
        value = row.get(f["source"])
        converted, reason = _convert_value(f, value)
        if reason:
            quarantine.append({"source_key": {k: row.get(k) for k in key_cols},
                               "field": f["source"], "reason": reason})
        if converted is _OMIT:
            continue
        doc[f["target"]] = converted
    return doc


def _build_key(row: dict[str, Any], key: dict) -> Any:
    src = key.get("source", [])
    tgt = key.get("target", [])
    if isinstance(tgt, str):
        tgt = [tgt]
    vals = [row.get(c) for c in src]
    if len(src) == 1:
        return vals[0]
    return {t: v for t, v in zip(tgt, vals)}


def _select(conn, sql: str, params: dict | None = None) -> list[dict[str, Any]]:
    cur = conn.cursor()
    cur.execute(sql, params or {})
    cols = [d[0].upper() for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_$#]*$")
_TABLE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_$#]*(\.[A-Za-z_][A-Za-z0-9_$#]*)*$")
_PARAM_VALUE_RE = re.compile(r"^[A-Za-z0-9_.:@-]+$")
# Mirrors the recon harness (recon/config.py READ_ONLY_PREDICATE_KEYWORDS);
# kept as a copy so the loader has no plugin dependency.
_READ_ONLY_PREDICATE_KEYWORDS = re.compile(
    r"\b(insert|update|delete|merge|drop|alter|create|truncate|grant|revoke|call|"
    r"exec|execute|copy|unload|into|union|lock|skip\s+locked|for\s+update|wait\s+\d+|"
    r"updlock|xlock|holdlock|tablock|tablockx|rowlock|paglock|readcommittedlock|"
    r"serializable|repeatableread)\b",
    re.IGNORECASE)
_SQL_NOISE = re.compile(r"'(?:[^']|'')*'|/\*.*?\*/|--[^\r\n]*", re.DOTALL)


def _validate_identifier(name: str) -> str:
    if not _IDENT_RE.fullmatch(name or ""):
        raise ValueError(f"invalid identifier: {name!r}")
    return name


def _validate_table(name: str) -> str:
    if not _TABLE_RE.fullmatch(name or ""):
        raise ValueError(f"invalid table identifier: {name!r}")
    return name


def _validate_predicate(value: str) -> str:
    if any(tok in value for tok in (";", "--", "/*")):
        raise ValueError(f"predicate must be a single expression: {value!r}")
    keyword_text = _SQL_NOISE.sub(
        lambda m: "''" if m.group().startswith("'") else " ", value)
    if _READ_ONLY_PREDICATE_KEYWORDS.search(keyword_text):
        raise ValueError(f"predicate must be read-only: {value!r}")
    return value


def _quote_where(where: str) -> str:
    return f"({_validate_predicate(where)})"


def _field_source_cols(field_specs: list[dict]) -> list[str]:
    seen: list[str] = []
    for f in field_specs:
        if f["source"] not in seen:
            seen.append(f["source"])
    return seen


def _collection_stats() -> dict:
    return {"read": 0, "upserted": 0, "modified": 0, "deleted": 0,
            "quarantined": 0, "orphan_children": 0}


def load_collections(spec_path: str | Path, collection_names: list[str],
                     oracle_conn, mongo_db, params: dict | None = None) -> dict:
    """Load the named collections from `spec_path` into `mongo_db`.

    `params` substitutes ${name} placeholders in root_where/child_where, the
    same convention as the recon harness loader."""
    spec = json.loads(Path(spec_path).read_text())
    params = params or {}
    for k, v in params.items():
        if not _PARAM_VALUE_RE.fullmatch(str(v)):
            raise ValueError(f"invalid --param value for {k!r}")
    wanted = set(collection_names)
    stats: dict[str, dict] = {}
    quarantine_dir = QUARANTINE_DIR
    quarantine_dir.mkdir(parents=True, exist_ok=True)
    for coll in spec["collections"]:
        name = coll["collection"]
        if name not in wanted:
            continue
        st = _collection_stats()
        quarantine: list[dict] = []
        key = coll["key"]
        key_src = list(key.get("source", []))
        key_tgt = key.get("target", [])
        key_tgt = [key_tgt] if isinstance(key_tgt, str) else list(key_tgt)
        key_field_specs = {
            f["source"]: f for f in coll.get("decision", {}).get("key_fields", [])
        }
        field_specs = list(coll.get("fields", []))
        all_cols = key_src + [c for c in _field_source_cols(field_specs) if c not in key_src]
        embeds = coll.get("embeds", [])
        parent_ref_cols: set[str] = set()
        for emb in embeds:
            parent_ref_cols.update(emb.get("parent_ref") or key_src)
        sel_cols = all_cols + [c for c in parent_ref_cols if c not in all_cols]
        _validate_table(coll["root_table"])
        for c in sel_cols:
            _validate_identifier(c)
        sql = f"SELECT {', '.join(sel_cols)} FROM {coll['root_table']}"
        root_where = coll.get("root_where")
        if root_where:
            for k, v in params.items():
                root_where = root_where.replace("${" + k + "}", str(v))
            sql += " WHERE " + _quote_where(root_where)
        rows = _select(oracle_conn, sql)
        st["read"] = len(rows)
        key_cols = set(key_src)
        # Child rows per embed, grouped by their parent_key tuple.
        embed_rows: list[dict] = []
        for emb in embeds:
            e_parent_key = list(emb.get("parent_key", []))
            e_field_specs = list(emb.get("fields", [])) + list(emb.get("child_fields", []))
            e_cols = (e_parent_key
                      + [c for c in _field_source_cols(e_field_specs) if c not in e_parent_key]
                      + [c for c in emb.get("key", {}).get("source", []) if c not in e_parent_key])
            _validate_table(emb["child_table"])
            for c in e_cols:
                _validate_identifier(c)
            e_sql = f"SELECT {', '.join(dict.fromkeys(e_cols))} FROM {emb['child_table']}"
            child_where = emb.get("child_where")
            if child_where:
                for k, v in params.items():
                    child_where = child_where.replace("${" + k + "}", str(v))
                e_sql += " WHERE " + _quote_where(child_where)
            e_key_cols = list(emb.get("key", {}).get("source", []))
            order_cols = list(dict.fromkeys(
                e_parent_key + (e_key_cols or e_cols)))
            e_sql += " ORDER BY " + ", ".join(order_cols)
            grouped: dict[tuple, list[dict]] = {}
            for crow in _select(oracle_conn, e_sql):
                grouped.setdefault(tuple(crow.get(c) for c in e_parent_key), []).append(crow)
            embed_rows.append({"emb": emb, "grouped": grouped, "consumed": set()})
        target = mongo_db[name]
        live_key_forms: set[str] = set()
        for row in rows:
            _id = _build_key(row, key)
            doc: dict[str, Any] = {"_id": _id}
            if len(key_src) > 1:
                for s, t in zip(key_src, key_tgt):
                    kf = key_field_specs.get(s, {})
                    converted, reason = _convert_value(kf, row.get(s))
                    if reason:
                        quarantine.append({"source_key": {k: row.get(k) for k in key_src},
                                           "field": s, "reason": reason})
                    if converted is not _OMIT:
                        doc[t] = converted
            _apply_fields(row, field_specs, doc, quarantine, key_cols)
            for entry in embed_rows:
                emb = entry["emb"]
                parent_ref = emb.get("parent_ref") or key_src
                ref_tuple = tuple(row.get(c) for c in parent_ref)
                entry["consumed"].add(ref_tuple)
                children = entry["grouped"].get(ref_tuple, [])
                elements = []
                for crow in children:
                    edoc: dict[str, Any] = {}
                    ekey = emb.get("key", {})
                    efields = [f for f in emb.get("fields", []) + emb.get("child_fields", [])
                               if f["source"] not in emb.get("parent_key", [])]
                    _apply_fields(crow, efields, edoc, quarantine, key_cols)
                    esrc = ekey.get("source", [])
                    etgt = ekey.get("target", [])
                    if isinstance(etgt, str):
                        etgt = [etgt]
                    if len(esrc) == 1 and etgt:
                        edoc[etgt[0]] = crow.get(esrc[0])
                    elif esrc:
                        for t, s in zip(etgt, esrc):
                            edoc[t] = crow.get(s)
                    elements.append(edoc)
                if emb.get("shape", "array") == "subdocument":
                    if elements:
                        doc[emb["array_path"]] = elements[0]
                else:
                    doc[emb["array_path"]] = elements
            res = target.replace_one({"_id": _id}, doc, upsert=True)
            st["upserted"] += 1
            st["modified"] += res.modified_count or 0
            live_key_forms.add(json.dumps(_id, sort_keys=True, default=str))
        # Orphan children: rows in an embed group whose parent_ref tuple no
        # root row consumed. Quarantined to file, never written.
        orphan_children = 0
        for entry in embed_rows:
            emb = entry["emb"]
            child_key_cols = list(emb.get("key", {}).get("source", [])) or \
                list(emb.get("parent_key", []))
            for ref_tuple, rows_ in entry["grouped"].items():
                if ref_tuple in entry["consumed"]:
                    continue
                for crow in rows_:
                    quarantine.append({
                        "source_key": {k: crow.get(k) for k in child_key_cols},
                        "field": emb["array_path"],
                        "reason": "child row has no root row",
                    })
                    orphan_children += 1
        st["orphan_children"] += orphan_children
        # Converge: remove target docs no longer in the source key set,
        # scoped to target_where when the spec scopes the collection.
        removed = 0
        scope = json.loads(coll["target_where"]) if coll.get("target_where") else {}
        for existing in target.find(scope, {"_id": 1}):
            if json.dumps(existing["_id"], sort_keys=True, default=str) not in live_key_forms:
                target.delete_one({"_id": existing["_id"]})
                removed += 1
        st["deleted"] = removed
        st["quarantined"] = len(quarantine)
        qf = quarantine_dir / f"{name}.jsonl"
        if quarantine:
            with qf.open("w", encoding="utf-8") as fh:
                for item in quarantine:
                    fh.write(json.dumps(item, default=str) + "\n")
        elif qf.exists():
            qf.unlink()
        stats[name] = st
    return stats
