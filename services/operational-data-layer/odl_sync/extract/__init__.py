from dataclasses import dataclass, field
from collections import Counter
from typing import Any, Callable

from ..normalize import exception_id, match_key


@dataclass
class SourceRecord:
    source: str
    key: str
    name: str
    address: str
    data: dict[str, Any]
    raw: dict[str, str]
    dependents: list[tuple[str, str, dict]] = field(default_factory=list)


@dataclass
class Extract:
    source: str
    records: list[SourceRecord] = field(default_factory=list)
    unplaced: list[dict] = field(default_factory=list)
    checkpoint: float = 0


class ExtractError(Exception):
    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)


def duplicate_parent_keys(records):
    counts = Counter(match_key(record.name, record.address) for record in records)
    return {record.key for record in records if counts[match_key(record.name, record.address)] > 1}


def raw_strings(row):
    return {str(k): str(v) for k, v in row.items()}


def rejected(source, reason, key, row):
    keys = [f'{source}:{key}']
    return dict(_id=exception_id(reason, keys), reason=reason, customer_ids=[],
                source_keys=keys, detail=raw_strings(row), status='open')


def transform(result: Extract, rows, key: str, convert: Callable):
    for row in rows:
        try:
            yield convert(row)
        except (ValueError, TypeError, ArithmeticError, UnicodeError, KeyError):
            result.unplaced.append(rejected(result.source, 'transform_failed', row.get(key), row))


def sql_rows(cursor, query):
    cursor.execute(query)
    names = [col[0].lower() for col in cursor.description]
    while batch := cursor.fetchmany(2000):
        for row in batch:
            yield dict(zip(names, row))
