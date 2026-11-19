import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAYERS = ('bronze', 'silver', 'gold')
DOMAINS = ('billing', 'documents', 'users', 'audit', 'platform')


def data_root():
    ns = os.environ.get('NS', '')
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]*', ns):
        raise ValueError('NS is required and must contain lowercase letters, digits or hyphens')
    return ROOT / '.data' / ns


def database(layer, domain):
    if layer not in LAYERS or domain not in DOMAINS:
        raise ValueError('Unknown layer or domain')
    return f'{layer}_{domain}'


def delta_path(layer, domain, table):
    database(layer, domain)
    if not re.fullmatch(r'[a-zA-Z_][a-zA-Z_0-9]*', table):
        raise ValueError('Invalid table name')
    return data_root() / 'delta' / layer / domain / table.lower()


def initialize(spark):
    for layer in LAYERS:
        for domain in DOMAINS:
            path = data_root() / 'delta' / layer / domain
            path.mkdir(parents=True, exist_ok=True)
            spark.sql(f"CREATE DATABASE IF NOT EXISTS {database(layer, domain)} LOCATION '{path.as_uri()}'")
