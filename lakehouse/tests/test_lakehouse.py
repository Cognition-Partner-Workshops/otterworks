import csv
import os
import shutil
import uuid
from datetime import date

import pytest
from jinja2 import Environment, StrictUndefined
from pyspark.sql import types as T

from lakehouse.runtime.ingest import business_date, ingest, select_tables
from lakehouse.runtime.layout import DOMAINS, LAYERS, ROOT, data_root, database, delta_path
from lakehouse.runtime.session import create_session


@pytest.fixture(scope='module')
def spark():
    original = os.environ.get('NS')
    os.environ['NS'] = 'test-' + uuid.uuid4().hex
    session = create_session()
    yield session
    session.stop()
    shutil.rmtree(data_root())
    if original is None:
        del os.environ['NS']
    else:
        os.environ['NS'] = original


def test_layout(monkeypatch):
    monkeypatch.setenv('NS', 'sfx-d1110-after')
    for layer in LAYERS:
        for domain in DOMAINS:
            assert database(layer, domain) == f'{layer}_{domain}'
            assert delta_path(layer, domain, 'TABLE').relative_to(data_root()).as_posix() == f'delta/{layer}/{domain}/table'
    for ns in ('', '../unsafe', 'UPPER'):
        monkeypatch.setenv('NS', ns)
        with pytest.raises(ValueError):
            data_root()
    with pytest.raises(ValueError):
        database('invalid', 'billing')


def landing(tmp_path, day, rows):
    directory = tmp_path / 'billing' / 'CUSTOMER_ACCOUNT'
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f'{day}.psv'
    with path.open('w', newline='') as handle:
        csv.writer(handle, delimiter='|').writerows(rows)
    return path


def pilot(spark, day):
    env = Environment(undefined=StrictUndefined)
    macros = (ROOT / 'dbt/macros/legacy_text.sql').read_text()
    model = (ROOT / 'dbt/models/silver/billing/customer_account.sql').read_text()
    sql = env.from_string(macros + model).render(
        source=lambda *_: 'bronze_billing.customer_account', env_var=lambda _: day)
    return spark.sql(sql)


def test_ingestion_and_pilot(spark, tmp_path):
    row = ['1', '', 'Name|quoted\nline', 'ACTIVE', 'USD', '2026-11-09', 'A1', 'US', '']
    landing(tmp_path, '20261109', [row])
    for _ in range(2):
        ingest(spark, tmp_path, '20261109', ['CUSTOMER_ACCOUNT'])
        assert spark.table('bronze_billing.customer_account').count() == 1
    raw = spark.table('bronze_billing.customer_account').first()
    assert raw.owner_user_id is None and raw.region_cd == ''
    assert raw.account_name == row[2]
    assert raw._source_file.endswith('20261109.psv') and raw._ingested_at is not None
    result = pilot(spark, '20261109')
    assert isinstance(result.schema['customer_id'].dataType, T.LongType)
    assert isinstance(result.schema['created_dt'].dataType, T.DateType)
    assert tuple(result.first()) == (1, None, row[2], 'ACTIVE      ', 'USD', date(2026, 11, 9), 'A1', 'US', '')
    landing(tmp_path, '20261110', [['2', '3', 'New', 'CLOSED', 'EUR', '2026-11-10', 'A2', 'DE', 'EU']])
    ingest(spark, tmp_path, '20261110', ['CUSTOMER_ACCOUNT'])
    assert spark.table('bronze_billing.customer_account').count() == 2
    assert pilot(spark, '20261110').first().customer_id == 2
    landing(tmp_path, '20261110', [])
    ingest(spark, tmp_path, '20261110', ['CUSTOMER_ACCOUNT'])
    assert spark.table('bronze_billing.customer_account').count() == 1
    assert pilot(spark, '20261110').count() == 0
    landing(tmp_path, '20261111', [['bad']])
    with pytest.raises(ValueError, match='expected 9'):
        ingest(spark, tmp_path, '20261111', ['CUSTOMER_ACCOUNT'])
    with pytest.raises(FileNotFoundError):
        ingest(spark, tmp_path, '20261112', ['CUSTOMER_ACCOUNT'])
    row[0] = 'not-a-number'
    landing(tmp_path, '20261111', [row])
    ingest(spark, tmp_path, '20261111', ['CUSTOMER_ACCOUNT'])
    with pytest.raises(Exception, match='CAST_INVALID_INPUT'):
        pilot(spark, '20261111').collect()
    row[0], row[2] = '1', 'x' * 101
    landing(tmp_path, '20261111', [row])
    ingest(spark, tmp_path, '20261111', ['CUSTOMER_ACCOUNT'])
    assert pilot(spark, '20261111').first().account_name == 'x' * 100


def test_invalid_arguments():
    with pytest.raises(ValueError):
        select_tables(['missing'])
    for value in ('20260230', '2026-11-09', "20261109' OR true"):
        with pytest.raises(ValueError):
            business_date(value)
