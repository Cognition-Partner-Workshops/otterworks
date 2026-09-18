"""Shared pieces for the OW_BILLING -> MongoDB loaders.

Connections come from environment variables named in .migration/01_conventions.md
(ORACLE_BILLING_DSN, MONGO_LOCAL_URI); the values are never printed or written.
Oracle is opened read-only. Every value is converted the way the recon harness expects
(tolerance record tol-1): NUMBER(p,s) -> Decimal128, integer NUMBER -> long,
DATE/TIMESTAMP -> UTC date, CHAR right-trimmed, empty string -> missing,
CHAR(1) Y/N -> bool, *_CSV -> array, VARCHAR2 DD-MON-YY -> date with the raw text kept in
<field>_raw when it does not parse.
"""
from __future__ import annotations

import datetime as dt
import decimal
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

import oracledb
from bson.decimal128 import Decimal128
from pymongo import MongoClient
from pymongo.database import Database

oracledb.defaults.fetch_decimals = True

_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_YN_TRUE = {"Y", "T", "1", "TRUE", "YES"}
_YN_FALSE = {"N", "F", "0", "FALSE", "NO"}
# VARCHAR2 date columns: DD-MON-YY in the master tables, DD-MON-YY HH24:MI:SS from the history triggers.
_DATE_STRING_FORMATS = ("%d-%b-%y", "%d-%b-%y %H:%M:%S")


class LoaderError(Exception):
    pass


def _secret(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise LoaderError(f"secret '{name}' is not set in the environment; secrets are passed by name")
    return value


def oracle_connection(secret_name: str = "ORACLE_BILLING_DSN") -> oracledb.Connection:
    raw = _secret(secret_name)
    try:
        parsed = json.loads(raw)
        user, password, dsn = parsed["user"], parsed["password"], parsed["dsn"]
    except (json.JSONDecodeError, KeyError, TypeError):
        raise LoaderError(f"secret '{secret_name}' must be JSON with user, password, dsn") from None
    conn = oracledb.connect(user=user, password=password, dsn=dsn)
    cur = conn.cursor()
    cur.execute("SET TRANSACTION READ ONLY")
    cur.close()
    return conn


def mongo_database(database: str, allowed_targets: Path,
                   secret_name: str = "MONGO_LOCAL_URI") -> Database:
    allowed = json.loads(allowed_targets.read_text())
    if database not in allowed.get("databases", []):
        raise LoaderError(f"database '{database}' is not in {allowed_targets}; refusing to write")
    return MongoClient(_secret(secret_name))[database]


@dataclass
class FieldMap:
    source: str
    target: str
    source_type: str
    bson_type: str
    rules: list[str] = field(default_factory=list)


@dataclass
class EmbedMap:
    array_path: str
    child_table: str
    parent_key: list[str]
    key_source: list[str]
    key_target: str
    fields: list[FieldMap]


@dataclass
class CollectionMap:
    collection: str
    root_table: str
    key_source: list[str]
    key_target: list[str]
    fields: list[FieldMap]
    embeds: list[EmbedMap]


_ATTR_CREATED_DT = FieldMap("CREATED_DT", "createdDt", "DATE", "date")


def _fields(raw: list[dict]) -> list[FieldMap]:
    return [FieldMap(f["source"], f["target"], f.get("source_type", ""),
                     f.get("bson_type", ""), list(f.get("rules", []))) for f in raw]


def load_mapping(spec_path: Path) -> tuple[str, dict[str, CollectionMap]]:
    spec = json.loads(spec_path.read_text())
    out: dict[str, CollectionMap] = {}
    for c in spec["collections"]:
        key = c["key"]
        targets = [key["target"]] if isinstance(key["target"], str) else list(key["target"])
        embeds = []
        for e in c.get("embeds", []):
            ekey = e.get("key") or {}
            embeds.append(EmbedMap(e["array_path"], e["child_table"], list(e.get("parent_key", [])),
                                   list(ekey.get("source", [])), ekey.get("target", ""),
                                   _fields(e.get("fields", []))))
        out[c["collection"]] = CollectionMap(c["collection"], c["root_table"], list(key["source"]),
                                             targets, _fields(c["fields"]), embeds)
    return spec["version"], out


def _ident(name: str) -> str:
    if not _IDENT.match(name):
        raise LoaderError(f"refusing unsafe identifier {name!r}")
    return name


def convert(value: Any, f: FieldMap, raw_out: dict[str, Any]) -> Any:
    """Return the BSON value for one Oracle column value, or None when the field is omitted."""
    if value is None:
        return None
    if isinstance(value, str):
        if "rstrip_spaces" in f.rules:
            value = value.rstrip(" ")
        if value == "":
            return None
    if f.bson_type == "decimal":
        d = value if isinstance(value, decimal.Decimal) else decimal.Decimal(str(value))
        return Decimal128(d)
    if f.bson_type == "long":
        return int(value)
    if f.bson_type == "bool":
        token = str(value).strip().upper()
        if token in _YN_TRUE:
            return True
        if token in _YN_FALSE:
            return False
        return value
    if f.bson_type == "array":
        return [p.strip() for p in str(value).split(",") if p.strip() != ""]
    if f.bson_type == "date":
        if isinstance(value, dt.datetime):
            if value.tzinfo is not None:
                value = value.astimezone(dt.timezone.utc).replace(tzinfo=None)
            return value.replace(microsecond=(value.microsecond // 1000) * 1000)
        if isinstance(value, dt.date):
            return dt.datetime(value.year, value.month, value.day)
        if isinstance(value, str):
            for fmt in _DATE_STRING_FORMATS:
                try:
                    return dt.datetime.strptime(value.strip(), fmt)
                except ValueError:
                    continue
            raw_out[f"{f.target}_raw"] = value
            return None
    return value


def _select(table: str, columns: list[str], order_by: list[str]) -> str:
    cols = ", ".join(_ident(c) for c in columns)
    order = ", ".join(_ident(c) for c in order_by)
    return f"SELECT {cols} FROM {_ident(table)} ORDER BY {order}"


def _rows(conn: oracledb.Connection, sql: str, arraysize: int = 5000) -> Iterator[tuple]:
    cur = conn.cursor()
    cur.arraysize = arraysize
    cur.execute(sql)
    yield from cur
    cur.close()


def build_documents(conn: oracledb.Connection, cmap: CollectionMap) -> Iterator[dict[str, Any]]:
    """Stream root rows as documents, with embedded child arrays attached."""
    children: dict[tuple, list[dict[str, Any]]] = {}
    for e in cmap.embeds:
        cols = e.parent_key + e.key_source + [f.source for f in e.fields]
        for row in _rows(conn, _select(e.child_table, cols, e.parent_key + e.key_source)):
            pk = tuple(row[:len(e.parent_key)])
            elem: dict[str, Any] = {}
            raw: dict[str, Any] = {}
            for name, value in zip(e.key_source, row[len(e.parent_key):len(e.parent_key) + len(e.key_source)]):
                elem[e.key_target] = int(value) if isinstance(value, decimal.Decimal) else value
            for f, value in zip(e.fields, row[len(e.parent_key) + len(e.key_source):]):
                converted = convert(value, f, raw)
                if converted is not None:
                    elem[f.target] = converted
            elem.update(raw)
            children.setdefault((e.array_path, pk), []).append(elem)

    cols = cmap.key_source + [f.source for f in cmap.fields]
    for row in _rows(conn, _select(cmap.root_table, cols, cmap.key_source)):
        doc: dict[str, Any] = {}
        key_values = row[:len(cmap.key_source)]
        for target, value in zip(cmap.key_target, key_values):
            doc[target] = int(value) if isinstance(value, decimal.Decimal) and value == value.to_integral_value() else value
        raw: dict[str, Any] = {}
        for f, value in zip(cmap.fields, row[len(cmap.key_source):]):
            converted = convert(value, f, raw)
            if converted is not None:
                doc[f.target] = converted
        doc.update(raw)
        for e in cmap.embeds:
            doc[e.array_path] = children.get((e.array_path, tuple(key_values)), [])
        yield doc


# Attribute pattern (decision 2): ENTITY_ATTR_VALUE rows whose ENTITY_TYPE matches the root
# table are attached to the owning document as an `attributes` array. Values stay strings.
ATTRIBUTE_OWNERS: dict[str, str] = {"CUSTOMER_MASTER": "CUSTOMER"}


def load_attributes(conn: oracledb.Connection, entity_type: str) -> dict[str, list[dict[str, Any]]]:
    sql = ("SELECT ENTITY_ID, ATTR_NAME, ATTR_VALUE, ATTR_TYPE, CREATED_DT FROM ENTITY_ATTR_VALUE "
           "WHERE ENTITY_TYPE = :et ORDER BY ENTITY_ID, ATTR_NAME, EAV_ID")
    cur = conn.cursor()
    cur.arraysize = 5000
    cur.execute(sql, et=entity_type)
    out: dict[str, list[dict[str, Any]]] = {}
    for entity_id, name, value, attr_type, created in cur:
        attr: dict[str, Any] = {"name": name}
        if value not in (None, ""):
            attr["value"] = value
        if attr_type not in (None, ""):
            attr["type"] = attr_type
        raw: dict[str, Any] = {}
        converted = convert(created, _ATTR_CREATED_DT, raw)
        if converted is not None:
            attr["createdDt"] = converted
        attr.update(raw)
        out.setdefault(entity_id, []).append(attr)
    cur.close()
    return out


def load_collection(conn: oracledb.Connection, db: Database, cmap: CollectionMap,
                    batch_size: int = 2000) -> dict[str, int]:
    """Drop and reload one collection. Returns counts for the load log."""
    db.drop_collection(cmap.collection)
    coll = db[cmap.collection]
    n_docs = n_elems = n_raw = n_attrs = 0
    attributes: dict[str, list[dict[str, Any]]] = {}
    if cmap.root_table in ATTRIBUTE_OWNERS and len(cmap.key_target) == 1:
        attributes = load_attributes(conn, ATTRIBUTE_OWNERS[cmap.root_table])
    batch: list[dict[str, Any]] = []
    for doc in build_documents(conn, cmap):
        n_raw += sum(1 for k in doc if k.endswith("_raw"))
        for e in cmap.embeds:
            n_elems += len(doc.get(e.array_path, []))
        if attributes:
            attrs = attributes.get(doc[cmap.key_target[0]])
            if attrs:
                doc["attributes"] = attrs
                n_attrs += len(attrs)
        batch.append(doc)
        if len(batch) >= batch_size:
            coll.insert_many(batch, ordered=False)
            n_docs += len(batch)
            batch = []
    if batch:
        coll.insert_many(batch, ordered=False)
        n_docs += len(batch)
    if len(cmap.key_target) > 1:
        coll.create_index([(k, 1) for k in cmap.key_target], unique=True)
    return {"documents": n_docs, "embedded_elements": n_elems, "unparseable_dates": n_raw,
            "attached_attributes": n_attrs}
