import pytest

from parity.evidence_unt10_addendum import Queries, guard, merge_checks


@pytest.mark.parametrize('sql', ['MERGE INTO t', 'UPDATE t SET x=1', 'INSERT INTO t SELECT 1',
    'DELETE FROM t', 'CREATE TABLE t(x INT)', 'ALTER TASK t RESUME', 'EXECUTE TASK t',
    'CALL p()', '', 'SELECT 1; DELETE FROM t', '-- comment\nSELECT 1'])
def test_guard_rejects_writes_before_cursor(sql):
    with pytest.raises(ValueError):
        Queries(None).run(sql)


@pytest.mark.parametrize('sql', ['SELECT 1', 'SHOW TASKS', 'DESCRIBE TABLE t', "SELECT ';'"])
def test_guard_accepts_reads(sql):
    guard(sql)


def test_merge_checks():
    from parity.commands import mark_sql
    sql = mark_sql() % tuple(["'f'", "'m'", "'migrations-page'"] + ['NULL'] * 13)
    checks = merge_checks(sql)
    assert all(checks.values())
    assert checks['literals'] == {'folder': 'f', 'mapping': 'm', 'owner': 'migrations-page'}
    assert not merge_checks(sql + ' WHEN NOT MATCHED THEN INSERT VALUES (1)')['no_insert_delete']
    assert merge_checks('')['literals'] is None
