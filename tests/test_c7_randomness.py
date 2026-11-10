import importlib.util
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock

import pytest


SEED_DIR = Path(__file__).resolve().parents[1] / 'testdata/generated/seed'
FIXED_NOW = datetime(2026, 7, 1, tzinfo=timezone.utc)


def capture_seed(directory, module_name):
    saved = sys.modules.get('helpers')
    try:
        spec = importlib.util.spec_from_file_location('helpers', directory / 'helpers.py')
        helpers = importlib.util.module_from_spec(spec)
        sys.modules['helpers'] = helpers
        spec.loader.exec_module(helpers)
        helpers.now = lambda: FIXED_NOW
        helpers.days_ago = lambda n: FIXED_NOW - timedelta(days=n)
        helpers.hours_ago = lambda n: FIXED_NOW - timedelta(hours=n)
        helpers.hash_password = lambda password: password
        captured = {}

        def bulk_insert(cur, table, columns, rows, **kwargs):
            captured[table] = [dict(zip(columns, row)) for row in rows]
            return len(rows)

        helpers.bulk_insert = bulk_insert
        spec = importlib.util.spec_from_file_location(module_name, directory / f'{module_name}.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        cur = Mock()
        cur.fetchall.return_value = [(id, FIXED_NOW - timedelta(days=365)) for id in helpers.ADMIN_USER_IDS]
        module.seed(cur, 'c7')
        return captured, module
    finally:
        if saved is None:
            sys.modules.pop('helpers', None)
        else:
            sys.modules['helpers'] = saved


def synthetic_bytes(captured):
    excluded = {'password_hash', 'mfa_secret', 'token_id'}

    def encode(value):
        if isinstance(value, datetime):
            return value.isoformat()
        if hasattr(value, 'adapted'):
            return value.adapted
        return str(value)

    public = {table: [{k: v for k, v in row.items() if k not in excluded} for row in rows]
              for table, rows in captured.items()}
    return json.dumps(public, default=encode, sort_keys=True).encode()


@pytest.mark.parametrize('name', ['seed_01_users', 'seed_04_refresh_tokens'])
def test_synthetic_fields_repeat_but_credentials_do_not(name):
    first, _ = capture_seed(SEED_DIR, name)
    second, _ = capture_seed(SEED_DIR, name)
    assert synthetic_bytes(first) == synthetic_bytes(second)
    if name == 'seed_01_users':
        assert first['users'][0]['password_hash'] != second['users'][0]['password_hash']
        left = [row['mfa_secret'] for row in first['users'] if row['mfa_enabled']]
        right = [row['mfa_secret'] for row in second['users'] if row['mfa_enabled']]
        assert left and left != right
        assert all(len(secret) == 32 and set(secret) <= set('ABCDEFGHIJKLMNOPQRSTUVWXYZ234567') for secret in left)
    else:
        tokens = [row['token_id'] for row in first['refresh_tokens']]
        assert len(tokens) == len(set(tokens))
        assert all(len(token) == 35 and token.startswith('rt_') for token in tokens)
        assert tokens != [row['token_id'] for row in second['refresh_tokens']]


def test_empty_refresh_population_does_not_generate_credentials(monkeypatch):
    _, module = capture_seed(SEED_DIR, 'seed_04_refresh_tokens')
    monkeypatch.setattr(module, 'NUM_AUTH_USERS', 0)
    monkeypatch.setattr(module.secrets, 'token_hex', Mock(side_effect=AssertionError('unexpected credential')))
    assert module.seed(Mock(), 'c7') == 0
