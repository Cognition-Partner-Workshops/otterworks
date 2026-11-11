"""Runtime values reach Snowflake as bind parameters, never as SQL text."""
import importlib.util
import sys
from pathlib import Path

import pytest

BILLING = Path(__file__).resolve().parents[1] / 'billing'
sys.path.insert(0, str(BILLING))
# Bind migration/dw-exit/parity before capture.py puts warehouse/ (another parity) on the path.
import parity.connection  # noqa: E402,F401
import parity.ladder  # noqa: E402,F401


def load(name):
    spec = importlib.util.spec_from_file_location('billing_' + name, BILLING / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CAPTURE = load('capture')
REPORTS = load('reports')


class Cursor:
    sfqid = 'query-1'

    def __init__(self, rows):
        self.calls, self.rows = [], rows

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self.calls.append((sql, params))

    def executemany(self, sql, rows):
        self.calls.append((sql, None))

    def fetchone(self):
        return (len(self.rows),)

    def fetchall(self):
        return list(self.rows)


class Connection:
    def __init__(self, rows):
        self.cursor_ = Cursor(rows)

    def cursor(self):
        return self.cursor_


@pytest.mark.parametrize('columns', [
    [('ID', 'NUMBER(38,0); DROP TABLE X')],
    [('ID', "VARCHAR) COMMENT = 'x'")],
    [('ID"; DROP TABLE X; --', 'DATE')],
])
def test_column_ddl_rejects_untrusted_names_and_types(columns):
    with pytest.raises(ValueError):
        CAPTURE.column_ddl(columns)


def test_column_ddl_accepts_every_type_capture_emits():
    kinds = [CAPTURE.snow_type(t) for t in ('numeric(14,2)', 'bigint', 'date', 'timestamp without time zone',
                                             'text', 'character(3)', 'character varying(40)')]
    kinds += ['NUMBER(38,0)', 'NUMBER(38,2)', 'NUMBER(14,2)', 'VARCHAR(10)', 'VARCHAR(3)', 'VARCHAR(7)']
    assert CAPTURE.column_ddl([(f'C{i}', k) for i, k in enumerate(kinds)]).count('"C') == len(kinds)


def test_upload_binds_table_name_and_comment():
    connection = Connection([(1, 'USD')])
    CAPTURE.upload(connection, 'INVOICE_HDR', [('ID', 'NUMBER'), ('CURRENCY_CD', 'VARCHAR(3)')], [(1, 'USD')])
    calls = connection.cursor_.calls
    target = 'SFX_D1110_AFTER.TD_BASELINE."INVOICE_HDR"'
    executed = [(sql, params) for sql, params in calls if params is not None]
    assert executed[0] == ('CREATE TABLE IDENTIFIER(?) ("ID" NUMBER(38,0), "CURRENCY_CD" VARCHAR(3)) COMMENT = ?',
                           (target, CAPTURE.COMMENT))
    assert all(CAPTURE.COMMENT not in sql for sql, _ in calls)
    assert [p for _, p in executed[1:]] == [(target,), (target,)]


def test_export_queries_bind_the_business_date():
    for sql, parameters in REPORTS.converted_queries('20261109').values():
        assert '20261109' not in sql and parameters == ('20261109',) * sql.count('?')
    with pytest.raises(ValueError):
        REPORTS.converted_queries("20261109') OR 1=1 --")
