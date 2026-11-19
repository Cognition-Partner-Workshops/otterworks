"""m_SFX_AUDIT_DAILY_SUMMARY Snowpark job against Snowpark local testing (no Snowflake connection)."""
import datetime as dt
from decimal import Decimal
import importlib.util
from pathlib import Path

import pytest
from snowflake.snowpark import Session
from snowflake.snowpark.mock import ColumnEmulator, ColumnType, patch
from snowflake.snowpark.types import LongType, StringType, StructField, StructType, TimestampType

spec = importlib.util.spec_from_file_location(
    'm_sfx_audit_daily_summary', Path(__file__).resolve().parents[2] / 'snowpark/m_sfx_audit_daily_summary.py')
job = importlib.util.module_from_spec(spec)
spec.loader.exec_module(job)

EVENTS = StructType([StructField('EVENT_ID', LongType()), StructField('CUSTOMER_ID', LongType()),
                     StructField('EVENT_TS', TimestampType()), StructField('EVENT_TYPE', StringType())])


@patch('rtrim')
def rtrim(column: ColumnEmulator, *_) -> ColumnEmulator:
    # Snowpark local testing has no RTRIM.
    return ColumnEmulator(column.str.rstrip(' '), sf_type=ColumnType(StringType(), True))


D1, D2 = dt.date(2026, 11, 9), dt.date(2026, 11, 10)


def at(day, hour):
    return dt.datetime.combine(day, dt.time(hour))


@pytest.fixture
def session():
    with Session.builder.config('local_testing', True).create() as session:
        yield session


def load(session, rows):
    database = session.get_current_database()
    session.create_dataframe(rows, schema=EVENTS).write.save_as_table([database, *job.SOURCE], mode='overwrite')


def summary(session):
    rows = session.table([session.get_current_database(), *job.TARGET]).collect()
    # Local testing returns NUMBER columns as Decimal.
    rows = [tuple(int(v) if isinstance(v, Decimal) else v for v in row) for row in rows]
    return sorted(rows, key=lambda row: row[0])


FIRST = [(1, 7, at(D1, 1), 'DOC_EXPORT'), (2, 7, at(D1, 23), 'DOC_VIEW'), (3, 8, at(D1, 5), 'DOC_EXPORT  '),
         (4, 7, at(D2, 0), 'doc_export'), (5, None, at(D2, 3), 'DOC_EXPORT'), (6, None, at(D2, 4), None)]


def test_first_load_groups_counts_and_sequence_from_current_value(session):
    load(session, FIRST)
    assert job.run(session) == 4
    assert summary(session) == [(50001, D1, 7, 2, 1), (50002, D1, 8, 1, 1),
                                (50003, D2, 7, 1, 0), (50004, D2, None, 2, 1)]


def test_rerun_keeps_ids_refreshes_counts_and_removes_empty_groups(session):
    load(session, FIRST)
    job.run(session)
    assert job.run(session) == 4
    assert summary(session)[0] == (50001, D1, 7, 2, 1)
    load(session, [row for row in FIRST if row[0] != 3] + [(9, 7, at(D1, 2), 'DOC_EXPORT'), (8, 9, at(D1, 2), 'LOGIN')])
    assert job.run(session) == 4
    assert summary(session) == [(50001, D1, 7, 3, 2), (50003, D2, 7, 1, 0),
                                (50004, D2, None, 2, 1), (50005, D1, 9, 1, 0)]

