"""Quote identifiers for local schema-qualified DuckDB relations."""


def quote(name):
    if not isinstance(name, str) or not name or '\x00' in name:
        raise ValueError('Expected a nonempty identifier without NUL')
    return '"' + name.replace('"', '""') + '"'


def relation(name):
    parts = name.split('.')
    if len(parts) != 2:
        raise ValueError('Expected schema.relation')
    return '.'.join(map(quote, parts))
