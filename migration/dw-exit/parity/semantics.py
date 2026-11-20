"""Comparison rules derived from the checked-in Teradata relation definitions."""
from functools import lru_cache
from pathlib import Path
import re

import sqlglot
from sqlglot import exp

ROOT = Path(__file__).resolve().parents[3]


@lru_cache(maxsize=None)
def columns(relation):
    name = relation.upper().replace('SFX_PC_BILLING.', 'SFX_BILLING.')
    if '.' not in name:
        name = 'SFX_BILLING.' + name
    for path in sorted((ROOT / 'warehouse/teradata/ddl').rglob('*.sql')):
        text = path.read_text()
        for match in re.finditer(r'CREATE\s+(?:MULTISET\s+|SET\s+)?TABLE\s+([\w.]+).*?\((.*?)\)\s*(?:UNIQUE\s+)?(?:PRIMARY|NO PRIMARY)\s+INDEX', text, re.S | re.I):
            if match[1].upper() != name:
                continue
            result = {}
            for line in match[2].splitlines():
                col = re.match(r'\s*(\w+)\s+((?:VAR)?CHAR)\s*\((\d+)\)(.*)', line, re.I)
                if col:
                    result[col[1].upper()] = {'char': col[2].upper() == 'CHAR',
                        'case_insensitive': bool(re.search(r'NOT CASESPECIFIC', col[4], re.I))}
            return result
        for match in re.finditer(r'CREATE\s+VIEW\s+([\w.]+)\s+AS\s+(.*?);', text, re.S | re.I):
            if match[1].upper() != name:
                continue
            query = sqlglot.parse_one(re.sub(r'LOCKING ROW FOR ACCESS', '', match[2], flags=re.I), read='teradata')
            tables = {t.alias_or_name.upper(): (t.db + '.' + t.name).upper() for t in query.find_all(exp.Table)}
            result = {}
            for selection in query.expressions:
                value = selection.this if isinstance(selection, exp.Alias) else selection
                if isinstance(value, exp.Cast) and value.args['to'].this == exp.DataType.Type.CHAR:
                    result[selection.alias_or_name.upper()] = {'char': True, 'case_insensitive': False}
                if isinstance(value, exp.Column):
                    candidates = [tables[value.table.upper()]] if value.table else list(tables.values())
                    rules = [columns(t)[value.name.upper()] for t in candidates if value.name.upper() in columns(t)]
                    if len(rules) == 1:
                        result[selection.alias_or_name.upper()] = rules[0]
            return result
    return {}


def char_columns(relation):
    return sorted(name for name, rule in columns(relation).items() if rule['char'])


def numeric_type(values, precision, scale):
    if scale is None:
        scale = max((max(0, -v.as_tuple().exponent) for v in values if v is not None), default=0)
    if scale > 38:
        raise ValueError('Source numeric scale exceeds DuckDB decimal precision')
    return f'DECIMAL({precision or 38},{scale})'
