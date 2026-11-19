"""SQL composition for warehouse tools; data values belong in driver parameters."""

import re

from psycopg import sql


def identifier(value, dialect='snowflake', *, qualified=True, preserve_case=False):
    if dialect not in ('snowflake', 'postgres', 'sqlite'):
        raise ValueError(f'Unsupported SQL dialect: {dialect}')
    parts = value.split('.') if isinstance(value, str) and qualified else [value]
    if not parts or any(not isinstance(p, str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_$]*', p)
                        for p in parts):
        raise ValueError(f'Invalid identifier: {value}')
    if not preserve_case:
        parts = [p.upper() if dialect == 'snowflake' else p.lower() for p in parts]
    return sql.Identifier(*parts)


def compose(template, *parts, **named):
    """Render a trusted SQL template with composable identifiers/fragments only."""
    if any(not isinstance(part, sql.Composable) for part in (*parts, *named.values())):
        raise TypeError('SQL composition requires validated identifiers or SQL fragments')
    return sql.SQL(template).format(*parts, **named).as_string()


def stage(value):
    name, *path = value.removeprefix('@').split('/')
    if any(p in ('.', '..') or not re.fullmatch(r'[A-Za-z0-9_.-]*', p) for p in path):
        raise ValueError(f'Invalid stage path: {value}')
    suffix = '/' + '/'.join(path) if path else ''
    return sql.Composed([sql.SQL('@'), identifier(name), sql.SQL(suffix)])
