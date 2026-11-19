"""Validated SQL composition for migration clients."""

import re

from psycopg import sql


def identifier(value, dialect='snowflake', *, qualified=True, preserve_case=False):
    if dialect not in ('snowflake', 'postgres', 'duckdb'):
        raise ValueError(f'Unsupported dialect: {dialect}')
    parts = value.split('.') if isinstance(value, str) and qualified else [value]
    if not parts or any(not isinstance(p, str) or not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9$]*', p) for p in parts):
        raise ValueError(f'Invalid identifier: {value!r}')
    if not preserve_case:
        parts = [p.upper() if dialect == 'snowflake' else p.lower() for p in parts]
    return sql.Identifier(*parts)


def compose(template, *parts, **named):
    if any(not isinstance(p, sql.Composable) for p in (*parts, *named.values())):
        raise TypeError('Expected validated SQL components')
    return sql.SQL(template).format(*parts, **named).as_string()
