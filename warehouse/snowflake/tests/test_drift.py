import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
V008 = ROOT / 'migrations/V008__restore_usage_daily_currency_code.sql'


def test_usage_daily_currency_code_contract_is_three_characters():
    for spec in ('fixture_columns.yml', 'landing_columns.yml'):
        columns = yaml.safe_load((ROOT / spec).read_text())['billing']['USAGE_DAILY']
        assert columns['CURRENCY_CODE'] == 'CHAR(3)'
    v007 = (ROOT / 'migrations/V007__shared_seed.sql').read_text()
    assert not re.search(r'USAGE_DAILY ALTER COLUMN CURRENCY_CODE', v007)


def test_v008_restores_currency_code_without_replacing_the_table():
    sql = V008.read_text()
    body = sql.split('$$')[1]
    assert 'ADD COLUMN IF NOT EXISTS CURRENCY_CODE_SFX_D1110 CHAR(3)' in body
    assert 'RENAME COLUMN CURRENCY_CODE_SFX_D1110 TO CURRENCY_CODE' in body
    assert body.index('UPDATE RAW_BILLING.USAGE_DAILY SET CURRENCY_CODE_SFX_D1110 = CURRENCY_CODE') \
        < body.index('DROP COLUMN CURRENCY_CODE') < body.rindex('RENAME COLUMN')
    assert 'IF (declared_length = 3 AND rebuild_columns = 0)' in body and 'RETURN' in body
    assert 'LENGTH(CURRENCY_CODE) > 3' in body and 'RAISE overlength_values' in body
    assert body.index('RAISE overlength_values') < body.index('ADD COLUMN')
    assert body.count('RENAME COLUMN CURRENCY_CODE_SFX_D1110 TO CURRENCY_CODE') == 2
    resume = body.index('IF (declared_length IS NULL AND rebuild_columns = 1)')
    assert resume < body.index('RENAME COLUMN') < body.index('LENGTH(CURRENCY_CODE) > 3')
    for forbidden in ('CREATE OR REPLACE TABLE', 'CREATE TABLE', 'TRUNCATE', 'DELETE FROM', 'DROP TABLE'):
        assert forbidden not in sql.upper()
    assert sql.count('$$') == 2 and sql.rstrip().endswith('$$;')
    assert re.search(r"COMMENT 'sfx-d1110[^']*'", body)
