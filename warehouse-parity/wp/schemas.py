"""Snowflake schema prefix: run the harness against MIG_DW, MIG_STG, ... instead of DW, STG, ...

With WP_SF_SCHEMA_PREFIX set, every statement sent to Snowflake has the harness schemas
(DW, STG, AUDIT, PARITY) renamed in identifier positions only: a schema qualifier
(`dw.t`, `DW."ClaimStatusRef"`, `db.dw.t`) or the name after the SCHEMA keyword
(`CREATE SCHEMA IF NOT EXISTS DW`, `USE SCHEMA dw`). String literals, comments and
quoted identifiers other than the exact upper-case "DW" are left alone, and nothing else
in the statement changes. Unset or empty prefix = statements pass through untouched.
"""
import os
import re

SCHEMAS = ("DW", "STG", "AUDIT", "PARITY")
PREFIX_OK = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

_TOKEN = re.compile(r"""
    (?P<ws>\s+)
  | (?P<comment>--[^\n]*|//[^\n]*|/\*.*?(?:\*/|\Z))
  | (?P<string>'(?:[^'\\]|\\.|'')*(?:'|\Z))
  | (?P<quoted>"(?:[^"]|"")*(?:"|\Z))
  | (?P<dollar>\$\$)
  | (?P<word>[A-Za-z_][A-Za-z0-9_$]*)
  | (?P<other>.)
""", re.S | re.X)
_QUALIFIED = re.compile(r"\b(" + "|".join(SCHEMAS) + r")\s*\.\s*[\"A-Za-z_]", re.I)


def prefix():
    p = os.environ.get("WP_SF_SCHEMA_PREFIX", "").strip()
    if p and not PREFIX_OK.match(p):
        raise ValueError(f"WP_SF_SCHEMA_PREFIX must be a plain identifier prefix: {p!r}")
    return p


def tokens(sql):
    return [(m.lastgroup, m.group()) for m in _TOKEN.finditer(sql)]


def _schema_of(kind, text):
    """Canonical schema name if this token names one of the harness schemas."""
    if kind == "word" and text.upper() in SCHEMAS:
        return text.upper()
    if kind == "quoted" and text[1:-1] in SCHEMAS:
        return text[1:-1]
    return None


def _renamed(kind, schema, pfx):
    name = pfx + schema
    return f'"{name}"' if kind == "quoted" else name


def _is_name(tok):
    return tok[0] in ("word", "quoted")


def _schema_positions(toks):
    """Indexes of tokens used as a schema name: a qualifier, or the name after SCHEMA [IF [NOT] EXISTS]."""
    sig = [i for i, (k, _) in enumerate(toks) if k not in ("ws", "comment", "dollar")]

    def at(j):
        return toks[sig[j]] if 0 <= j < len(sig) else (None, "")

    def dot(j):
        return at(j) == ("other", ".")

    for j, i in enumerate(sig):
        if not _is_name(toks[i]):
            continue
        if dot(j + 1) and _is_name(at(j + 2)):
            # schema.object or db.schema.object; never object.column or deeper parts
            first_of_three = not dot(j - 1) and dot(j + 3) and _is_name(at(j + 4))
            if (not dot(j - 1) or (_is_name(at(j - 2)) and not dot(j - 3))) and not first_of_three:
                yield i
            continue
        k = j - 1
        if dot(k) and _is_name(at(k - 1)):
            k -= 2
        if at(k)[0] == "word" and at(k)[1].upper() == "EXISTS":
            k -= 1
            if at(k)[1].upper() == "NOT":
                k -= 1
            if at(k)[1].upper() == "IF":
                k -= 1
        if at(k)[0] == "word" and at(k)[1].upper() == "SCHEMA" and toks[i][1].upper() not in ("IF", "NOT", "EXISTS"):
            yield i


def remap(sql, pfx=None):
    """Rename DW/STG/AUDIT/PARITY to <prefix>DW/... wherever they are used as a schema name."""
    pfx = prefix() if pfx is None else pfx
    if not pfx or not sql:
        return sql
    toks = tokens(sql)
    out = [t for _, t in toks]
    for i in _schema_positions(toks):
        schema = _schema_of(*toks[i])
        if schema:
            out[i] = _renamed(toks[i][0], schema, pfx)
    return "".join(out)


def harness_schemas_used(sql, pfx=""):
    """Harness schemas (prefixed or not) a statement names in identifier position, as Snowflake resolves them."""
    known = set(SCHEMAS) | {pfx.upper() + x for x in SCHEMAS}
    toks = tokens(sql)
    names = {toks[i][1][1:-1] if toks[i][0] == "quoted" else toks[i][1].upper() for i in _schema_positions(toks)}
    return sorted(names & known)


def schema_name(schema, pfx=None):
    """Remap one bare schema name, e.g. for information_schema lookups."""
    pfx = prefix() if pfx is None else pfx
    return pfx + schema.upper() if pfx and schema.upper() in SCHEMAS else schema


def literal_refs(sql):
    """Unprefixed schema-qualified names hiding inside string literals (dynamic SQL), which remap leaves alone."""
    return sorted({m.group(1).upper() + "." for k, t in tokens(sql) if k == "string"
                   for m in _QUALIFIED.finditer(t)})
