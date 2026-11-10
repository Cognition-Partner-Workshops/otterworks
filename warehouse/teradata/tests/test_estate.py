import io
import csv
import datetime as dt
import os
import subprocess
import sys
import uuid
from pathlib import Path

import psycopg
from psycopg import sql
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from seed.columns import TABLES
from seed.generate import extra_count
from bteq import Runner
from bteq.load import CONTROL_ROOT, load_all, load_control, parse_control
from bteq.setup import setup


@pytest.fixture
def estate(td):
    name = 'estate_' + uuid.uuid4().hex
    td.conn.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
    runner = Runner(connection=psycopg.connect(td.conn.info.dsn, dbname=name), output=io.StringIO())
    try:
        setup(runner)
        yield runner
    finally:
        runner.conn.close()
        td.conn.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(name)))


def test_generate_setup_load(estate, tmp_path):
    generator = Path(__file__).resolve().parents[2] / 'seed' / 'generate.py'
    generated = subprocess.run([sys.executable, str(generator), '--rows', '2000', '--seed', '1110', '--out', str(tmp_path)], text=True, capture_output=True)
    assert generated.returncode == 0, generated.stderr
    counts = load_all(estate, tmp_path)
    assert len(counts) == 40
    for table in TABLES:
        path = tmp_path / table.area / table.name / '20261109.psv'
        with path.open() as handle:
            expected = sum(1 for _ in handle)
        target = table.database.lower() + '.stg_' + table.name.lower()
        actual = estate.conn.execute(sql.SQL('SELECT count(*) FROM {}').format(sql.Identifier(*target.split('.')))).fetchone()[0]
        assert actual == counts[target] == expected == table.count(2000) + extra_count(table.name)
        core = table.database.lower() + '.' + table.name.lower()
        metadata = estate.conn.execute('SELECT is_set FROM sfx_td.tables WHERE name=%s', (core,)).fetchone()
        assert metadata == (table.is_set,)
    assert estate.conn.execute("SELECT count(*) FROM pg_views WHERE schemaname IN ('sfx_billing','sfx_documents','sfx_users','sfx_audit')").fetchone() == (8,)
    setup(estate)
    assert load_all(estate, tmp_path) == counts
    for target, count in counts.items():
        assert estate.conn.execute(sql.SQL('SELECT count(*) FROM {}').format(sql.Identifier(*target.split('.')))).fetchone()[0] == count
    estate.execute('INSERT INTO SFX_DOCUMENTS.STORAGE_USAGE_DAILY SELECT * FROM SFX_DOCUMENTS.STG_STORAGE_USAGE_DAILY')
    assert estate.errorcode == 0, estate.output.getvalue()
    assert estate.activitycount == counts['sfx_documents.stg_storage_usage_daily'] - 50
    estate.execute('INSERT INTO SFX_USERS.APP_USER SELECT * FROM SFX_USERS.STG_APP_USER')
    assert estate.errorcode == 0, estate.output.getvalue()
    assert estate.conn.execute('SELECT min(length(display_name)),max(length(display_name)) FROM sfx_users.app_user WHERE user_id>=9000000001').fetchone() == (60, 60)


def test_loader_empty_and_errors(estate, tmp_path):
    path = CONTROL_ROOT / 'fastload' / 'billing_plan_catalog.fl'
    variables = {'LANDING_DIR': str(tmp_path), 'BUSINESS_DATE': '20261109'}
    control = parse_control(path, variables)
    control.path.parent.mkdir(parents=True)
    control.path.write_text('1|PRO|Pro|10.00|USD\n')
    assert load_control(estate, path, variables) == 1
    control.path.write_text('bad|PRO|Pro|10.00|USD\n')
    with pytest.raises(psycopg.errors.InvalidTextRepresentation):
        load_control(estate, path, variables)
    assert estate.conn.execute('SELECT count(*) FROM sfx_billing.stg_plan_catalog').fetchone() == (1,)
    control.path.write_text('1|too few\n')
    with pytest.raises(ValueError, match='fields'):
        load_control(estate, path, variables)
    control.path.write_text('')
    assert load_control(estate, path, variables) == 0
    assert estate.conn.execute('SELECT count(*) FROM sfx_billing.stg_plan_catalog').fetchone() == (0,)
    control.path.unlink()
    with pytest.raises(FileNotFoundError):
        load_control(estate, path, variables)


def test_control_validation(tmp_path):
    path = tmp_path / 'input.fl'
    path.write_text('INSERT INTO SFX_USERS.APP_USER (USER_ID) VALUES(:USER_ID);')
    with pytest.raises(ValueError, match='staging'):
        parse_control(path)
    path.write_text('INSERT INTO SFX_USERS.STG_APP_USER (USER_ID) VALUES(:DISPLAY_NAME);')
    with pytest.raises(ValueError, match='same order'):
        parse_control(path)


def test_daily_chain(estate, tmp_path):
    root = Path(__file__).resolve().parents[1]
    exports = tmp_path / 'exports'
    command = [sys.executable, str(root / 'jobs' / 'daily_chain'), '--rows', '2000',
               '--landing', str(tmp_path / 'landing'), '--exports', str(exports)]
    environment = {**os.environ, 'TD_PG_DSN': estate.conn.info.dsn, 'TD_PG_DB': estate.conn.info.dbname}
    result = subprocess.run(command, env=environment, text=True, capture_output=True, timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'audit/11_reconciliation | 0' in result.stdout
    assert estate.conn.execute('SELECT (SELECT count(*) FROM sfx_documents.stg_storage_usage_daily)-(SELECT count(*) FROM sfx_documents.storage_usage_daily)').fetchone() == (50,)
    assert estate.conn.execute('SELECT min(length(display_name)),max(length(display_name)) FROM sfx_users.app_user WHERE user_id>=9000000001').fetchone() == (60, 60)
    with (exports / 'subscription_plans.psv').open() as handle:
        plans = list(csv.reader(handle, delimiter='|'))
    assert len([r for r in plans if int(r[0]) >= 9000000001]) == 100
    with (exports / 'currency_daily.psv').open() as handle:
        currency = list(csv.reader(handle, delimiter='|'))
    assert len(currency) == 1 and int(currency[0][1]) == 2100
    with (exports / 'invoice_periods.psv').open() as handle:
        periods = {int(r[0]): r for r in csv.reader(handle, delimiter='|')}
    dates = ('2026-10-31', '2024-02-29', '2025-12-31', '2026-01-01', '1999-12-31', '2026-11-30')
    for index, value in enumerate(dates):
        date = dt.date.fromisoformat(value)
        row = periods[9000000001 + index]
        assert row[1:] == [(date-dt.timedelta(days=1)).isoformat(), str(date.month),
                           date.replace(day=1).strftime('%Y%m%d'), date.strftime('%Y-%m'), '2026-11-09']
    assert estate.conn.execute('SELECT count(*),count(DISTINCT document_id) FROM sfx_documents.doc_version WHERE document_id>=9000000001').fetchone() == (50, 50)
    assert estate.conn.execute("SELECT units FROM sfx_billing.usage_daily WHERE customer_id=9000000001 AND usage_type='STORAGE'").fetchone() == (1048576,)
    assert estate.conn.execute("SELECT count(*) FROM sfx_billing.invoice_line WHERE description='Monthly storage'").fetchone()[0] > 0
    assert estate.conn.execute('SELECT difference_count FROM sfx_audit.audit_recon WHERE recon_id=21000000001').fetchone() == (50,)
    assert estate.conn.execute("SELECT kind,count(*) FROM sfx_td.routines GROUP BY kind ORDER BY kind").fetchall() == [('MACRO', 6), ('PROCEDURE', 4)]
    for table in ('sfx_users.user_pref', 'sfx_documents.search_index_log', 'sfx_audit.audit_event_archive'):
        assert estate.conn.execute('SELECT count(*) FROM ' + table).fetchone() == (0,)
    again = subprocess.run(command + ['--reuse-landing'], env=environment, text=True, capture_output=True, timeout=120)
    assert again.returncode == 0, again.stdout + again.stderr


def test_chain_stops_on_load_error(estate, tmp_path):
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run([sys.executable, str(root / 'jobs' / 'daily_chain'), '--reuse-landing',
                             '--landing', str(tmp_path / 'absent'), '--exports', str(tmp_path / 'exports')],
                            env={**os.environ, 'TD_PG_DSN': estate.conn.info.dsn, 'TD_PG_DB': estate.conn.info.dbname},
                            text=True, capture_output=True, timeout=30)
    assert result.returncode == 1
    assert 'staging | 1' in result.stdout and 'users/01_load_users |' not in result.stdout
