import re

import yaml

from lakehouse.runtime.layout import ROOT

SPEC_ROOT = ROOT / 'parity' / 'specs'


def load_spec(path):
    spec = yaml.safe_load(path.read_text())
    if not isinstance(spec, dict) or not re.fullmatch(r'[a-z0-9][a-z0-9_.-]*', str(spec.get('id', ''))):
        raise ValueError('Spec id must be a stable lowercase filename-safe identifier')
    objects = spec.get('legacy_objects')
    if not isinstance(objects, list) or not objects or not all(isinstance(v, str) and ':' in v for v in objects):
        raise ValueError('legacy_objects requires nonempty coverage ids')
    keys = spec.get('keys')
    if not isinstance(keys, list) or not keys or any(not isinstance(k, str) or k != k.lower() for k in keys) or len(keys) != len(set(keys)):
        raise ValueError('keys requires unique lowercase column names')
    columns = spec.get('columns')
    if columns is not None and (not isinstance(columns, list) or not columns or
                               any(not isinstance(c, str) or c != c.lower() for c in columns) or
                               len(columns) != len(set(columns))):
        raise ValueError('columns requires unique lowercase column names')
    for field in ('normalize', 'tolerance', 'filters'):
        if not isinstance(spec.get(field, {}), dict):
            raise ValueError(f'{field} must be a mapping')
    for column, options in spec.get('normalize', {}).items():
        if not isinstance(options, dict) or set(options) - {
                'trim', 'rstrip', 'case_fold', 'empty_as_null', 'numeric_scale', 'date_format'}:
            raise ValueError(f'Invalid normalization options for {column}')
        if 'numeric_scale' in options and (type(options['numeric_scale']) is not int or not 0 <= options['numeric_scale'] <= 18):
            raise ValueError('numeric_scale must be an integer from 0 to 18')
    for label in ('legacy', 'lakehouse'):
        side = spec.get(label, {})
        kind = side.get('kind')
        required = {'postgres_sql': 'sql', 'spark_sql': 'sql', 'file': 'path',
                    'parquet': 'path', 'delta_table': 'table' if 'table' in side else 'path'}
        if kind not in required or not isinstance(side.get(required[kind]), str):
            raise ValueError(f'{label}: invalid reader kind or missing reader field')
        if kind == 'file':
            if not isinstance(side.get('header', False), bool) or len(side.get('delimiter', '|')) != 1:
                raise ValueError('file requires a boolean header and one-character delimiter')
    return spec


def discover(root=SPEC_ROOT):
    result = {}
    for path in sorted(root.glob('*/*.yaml')):
        spec = load_spec(path)
        if spec['id'] in result:
            raise ValueError(f'Duplicate spec id: {spec["id"]}')
        result[spec['id']] = (path, spec)
    return result
