"""Parity checks between a legacy golden and a DAG run, and the accepted differences.

A normalized snapshot is split into one check per compared thing; the check id
says what was compared:

  result.json exit_code
  s3.json s3://<bucket>/                     the bucket exists
  s3.json s3://<bucket>/<key>                one object (body, type, class, metadata)
  dynamodb.json <table> key_schema
  dynamodb.json <table>[<key>=<value>,...]   one item, by primary key
  sqs.json <queue>                           visible / in-flight counts
  postgres.json <table> columns|rows
  meilisearch.json <index> primary_key|settings|stats
  meilisearch.json <index>[<pk>=<value>]     one document

Each check is identical, an accepted difference (listed in the script's
reviewed accepted_differences.yaml with the exact before and after values) or
failed. A listed difference that does not occur, or occurs with other values,
is failed too: nothing is rounded up.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import yaml

from . import settings

IDENTICAL = "identical"
ACCEPTED = "accepted difference"
FAILED = "failed"

ACCEPTED_FILE = "accepted_differences.yaml"


class _Absent:
    def __repr__(self) -> str:
        return "<absent>"


ABSENT = _Absent()


def _attr_scalar(value) -> str:
    if isinstance(value, dict) and len(value) == 1:
        return str(next(iter(value.values())))
    return canon(value)


def _split_s3(value: dict) -> dict:
    out = {}
    for bucket, objects in value.items():
        out["s3.json s3://%s/" % bucket] = "present"
        for key, entry in (objects or {}).items():
            out["s3.json s3://%s/%s" % (bucket, key)] = entry
    return out


def _split_dynamodb(value: dict) -> dict:
    out = {}
    for table, data in value.items():
        key_names = data.get("key_schema") or []
        out["dynamodb.json %s key_schema" % table] = key_names
        for item in data.get("items") or []:
            ident = ",".join(
                "%s=%s" % (k, _attr_scalar(item.get(k))) for k in key_names
            )
            check, n = "dynamodb.json %s[%s]" % (table, ident), 2
            while check in out:
                check = "dynamodb.json %s[%s]#%d" % (table, ident, n)
                n += 1
            out[check] = item
    return out


def _split_postgres(value: dict) -> dict:
    out = {}
    for table, data in value.items():
        out["postgres.json %s columns" % table] = data.get("columns")
        out["postgres.json %s rows" % table] = data.get("rows")
    return out


def _split_meilisearch(value: dict) -> dict:
    out = {}
    for uid, data in value.items():
        pk = data.get("primary_key")
        for part in ("primary_key", "settings", "stats"):
            out["meilisearch.json %s %s" % (uid, part)] = data.get(part)
        for doc in data.get("documents") or []:
            ident = "%s=%s" % (pk, canon(doc.get(pk))) if pk else canon(doc)
            out["meilisearch.json %s[%s]" % (uid, ident)] = doc
    return out


SPLITTERS = {
    "result.json": lambda v: {"result.json %s" % k: x for k, x in v.items()},
    "s3.json": _split_s3,
    "dynamodb.json": _split_dynamodb,
    "sqs.json": lambda v: {"sqs.json %s" % q: x for q, x in v.items()},
    "postgres.json": _split_postgres,
    "meilisearch.json": _split_meilisearch,
}


def checks(files: dict[str, object]) -> dict[str, object]:
    """Split parsed surface files into {check id: value}."""
    out: dict[str, object] = {}
    order = list(SPLITTERS)
    for name, value in sorted(
        files.items(), key=lambda kv: (order.index(kv[0]) if kv[0] in order else len(order), kv[0])
    ):
        split = SPLITTERS.get(name)
        try:
            out.update(split(value) if split else {name: value})
        except (AttributeError, TypeError):
            out["%s (unexpected shape)" % name] = value
    return out


def canon(value) -> str:
    if value is ABSENT:
        return "<absent>"
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


@dataclass(frozen=True)
class Accepted:
    check: str
    before: object
    after: object
    reason: str

    def matches(self, before, after) -> bool:
        return canon(before) == canon(self.before) and canon(after) == canon(self.after)


@dataclass(frozen=True)
class Variant:
    """A flag-on run: a committed scenario's seed with Airflow Variable overrides."""

    name: str
    scenario: str
    variables: dict
    decision: str
    accepted: tuple[Accepted, ...]


@dataclass(frozen=True)
class AcceptedDifferences:
    script: str
    default: dict  # scenario name -> tuple[Accepted, ...], runs with default Variables
    variants: tuple[Variant, ...]

    def for_scenario(self, name: str) -> tuple[Accepted, ...]:
        return self.default.get(name, ())

    def variant(self, name: str) -> Variant:
        for v in self.variants:
            if v.name == name:
                return v
        raise KeyError("no variant %r in %s accepted differences" % (name, self.script))


ENTRY_KEYS = {"check", "before", "before_absent", "after", "after_absent", "reason"}
VARIANT_KEYS = {"name", "scenario", "variables", "decision", "accepted"}


def _side(entry: dict, side: str, where: str):
    has_value, absent = side in entry, entry.get("%s_absent" % side) is True
    if has_value == absent:
        raise ValueError("%s: give exactly one of %s / %s_absent: true" % (where, side, side))
    return ABSENT if absent else entry[side]


def _entries(raw, where: str, with_scenario: bool) -> list[tuple[str | None, Accepted]]:
    out = []
    seen = set()
    for i, entry in enumerate(raw or []):
        loc = "%s[%d]" % (where, i)
        keys = ENTRY_KEYS | ({"scenario"} if with_scenario else set())
        if not isinstance(entry, dict):
            raise ValueError("%s: expected a mapping" % loc)
        if set(entry) - keys:
            raise ValueError("%s: unknown keys %s" % (loc, sorted(set(entry) - keys)))
        for required in ("check", "reason") + (("scenario",) if with_scenario else ()):
            if not str(entry.get(required) or "").strip():
                raise ValueError("%s: %s is required" % (loc, required))
        acc = Accepted(
            check=entry["check"],
            before=_side(entry, "before", loc),
            after=_side(entry, "after", loc),
            reason=entry["reason"].strip(),
        )
        if canon(acc.before) == canon(acc.after):
            raise ValueError("%s: before and after are equal, nothing to accept" % loc)
        ident = (entry.get("scenario"), acc.check)
        if ident in seen:
            raise ValueError("%s: duplicate entry for %s" % (loc, acc.check))
        seen.add(ident)
        out.append((entry.get("scenario"), acc))
    return out


def load(script: str, path: Path | None = None) -> AcceptedDifferences:
    path = path or settings.GOLDEN_DIR / script / ACCEPTED_FILE
    data = yaml.safe_load(path.read_text()) or {}
    unknown = set(data) - {"script", "accepted", "variants"}
    if unknown:
        raise ValueError("%s: unknown keys %s" % (path, sorted(unknown)))
    if data.get("script") != script:
        raise ValueError("%s: script must be %r" % (path, script))
    default: dict = {}
    for scn, acc in _entries(data.get("accepted"), "%s accepted" % path, True):
        default.setdefault(scn, []).append(acc)
    variants = []
    for i, raw in enumerate(data.get("variants") or []):
        loc = "%s variants[%d]" % (path, i)
        if set(raw) - VARIANT_KEYS:
            raise ValueError("%s: unknown keys %s" % (loc, sorted(set(raw) - VARIANT_KEYS)))
        for required in ("name", "scenario", "variables", "decision"):
            if not raw.get(required):
                raise ValueError("%s: %s is required" % (loc, required))
        variants.append(
            Variant(
                name=raw["name"],
                scenario=raw["scenario"],
                variables=dict(raw["variables"]),
                decision=raw["decision"].strip(),
                accepted=tuple(a for _, a in _entries(raw.get("accepted"), loc, False)),
            )
        )
    names = [v.name for v in variants]
    if len(names) != len(set(names)):
        raise ValueError("%s: duplicate variant names" % path)
    return AcceptedDifferences(
        script=script,
        default={k: tuple(v) for k, v in default.items()},
        variants=tuple(variants),
    )


@dataclass(frozen=True)
class Row:
    case: str
    check: str
    before: object
    after: object
    result: str
    reason: str = ""


def classify(
    case: str,
    golden: dict[str, object],
    actual: dict[str, object],
    accepted: tuple[Accepted, ...] = (),
) -> list[Row]:
    """One row per check of the golden and the DAG run, golden order first."""
    before, after = checks(golden), checks(actual)
    by_check = {a.check: a for a in accepted}
    rows = []
    for check in list(before) + [c for c in after if c not in before]:
        b, a = before.get(check, ABSENT), after.get(check, ABSENT)
        entry = by_check.pop(check, None)
        if canon(b) == canon(a):
            if entry is None:
                rows.append(Row(case, check, b, a, IDENTICAL))
            else:
                rows.append(
                    Row(case, check, b, a, FAILED,
                        "listed accepted difference did not occur (%s)" % entry.reason)
                )
        elif entry is not None and entry.matches(b, a):
            rows.append(Row(case, check, b, a, ACCEPTED, entry.reason))
        elif entry is not None:
            detail = "before" if canon(b) != canon(entry.before) else "after"
            rows.append(
                Row(case, check, b, a, FAILED,
                    "differs from the reviewed accepted difference (%s value)" % detail)
            )
        else:
            rows.append(Row(case, check, b, a, FAILED, "not an accepted difference"))
    for check, entry in by_check.items():
        rows.append(
            Row(case, check, ABSENT, ABSENT, FAILED,
                "listed accepted difference did not occur, check absent in both runs (%s)"
                % entry.reason)
        )
    return rows


def _short(value, limit: int) -> str:
    text = canon(value)
    if len(text) <= limit:
        return text
    digest = hashlib.sha256(text.encode()).hexdigest()[:8]
    return "%s… (%d chars, sha256 %s)" % (text[: limit - 20], len(text), digest)


def leaf_differences(before, after, path: str = "") -> list[tuple[str, object, object]]:
    if isinstance(before, dict) and isinstance(after, dict):
        out = []
        for key in sorted(set(before) | set(after), key=str):
            out.extend(
                leaf_differences(
                    before.get(key, ABSENT), after.get(key, ABSENT), "%s.%s" % (path, key)
                )
            )
        return out
    if isinstance(before, list) and isinstance(after, list) and len(before) == len(after):
        out = []
        for i, (b, a) in enumerate(zip(before, after)):
            out.extend(leaf_differences(b, a, "%s[%d]" % (path, i)))
        return out
    if canon(before) == canon(after):
        return []
    return [(path.lstrip(".") or "value", before, after)]


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def display(row: Row, limit: int = 3) -> tuple[str, str]:
    if canon(row.before) == canon(row.after) or ABSENT in (row.before, row.after):
        return _short(row.before, 90), _short(row.after, 90)
    leaves = leaf_differences(row.before, row.after)
    shown = leaves[:limit]
    more = " (+%d more)" % (len(leaves) - limit) if len(leaves) > limit else ""
    return (
        "; ".join("%s=%s" % (p, _short(b, 60)) for p, b, _ in shown) + more,
        "; ".join("%s=%s" % (p, _short(a, 60)) for p, _, a in shown) + more,
    )


def markdown(rows: list[Row]) -> str:
    lines = [
        "| Scenario | What was compared | Before (legacy golden) | After (DAG) | Result |",
        "|---|---|---|---|---|",
    ]
    for row in rows:
        before, after = display(row)
        if row.result == IDENTICAL:
            result = IDENTICAL
        elif row.result == ACCEPTED:
            result = "accepted difference: %s" % row.reason
        else:
            result = "**failed**: %s" % row.reason
        lines.append(
            "| %s | `%s` | %s | %s | %s |"
            % tuple(_cell(x) for x in (row.case, row.check, before, after, result))
        )
    return "\n".join(lines) + "\n"


def summary(rows: list[Row]) -> dict[str, int]:
    out = {IDENTICAL: 0, ACCEPTED: 0, FAILED: 0}
    for row in rows:
        out[row.result] += 1
    return out
