from collections import Counter
from datetime import datetime

import pytest

from parity import evidence_unt5 as u
from parity.evidence import cell, full_compare


def test_fixture_integrity_and_routes():
    rows = u.read_psv(u.landing('seeded'))
    branches = u.route_rows(rows)
    assert len(rows) == 17
    assert Counter(r['route'] for r in branches) == {'critical': 7, 'standard': 5, 'default': 5}
    assert Counter(r['row_type'] for r in branches) == {1: 10, 3: 5, 0: 2}
    assert [r['values'][5] for r in branches if r['values'][0] == 107] == ['ESCALATED']
    assert [r['values'][5] for r in branches if r['values'][0] == 110] == ['OPEN']
    assert [r['values'][4] for r in branches if r['values'][0] == 113] == ['CRITICAL_TOO']
    assert u.sha(u.landing('frozen')) == u.FROZEN_SHA
    assert len(u.read_psv(u.landing('frozen'))) == 64
    assert len(u.read_psv(u.landing('dup_within_route'))) == 2


def test_seeded_expected_target():
    rows = u.read_psv(u.landing('seeded'))
    seed = u.read_psv(u.FIXTURES / 'seeded_target.psv')
    target = {r[0]: r for r in u.expected_target(seed, rows)}
    assert len(target) == 11
    assert target[101][5] == 'ESCALATED   '
    assert target[102][5] == 'OPEN        '
    assert target[103] == seed[2]
    assert target[104] == seed[3]
    assert target[114][1:3] == [25, 35]
    assert target[114][4:] == ['LOW         ', 'OPEN        ']
    assert target[108][5] is None
    assert target[107][1:4] == [None, None, None]
    assert 111 not in target and 112 not in target and 113 not in target and None not in target
    counts = u.expected_stats(seed, rows)
    assert counts['SECURITY_ALERT'] == {'inserted': 5, 'updated': 1, 'deleted': 0, 'rejected': 1}
    assert counts['SECURITY_ALERT1'] == {'inserted': 2, 'updated': 2, 'deleted': 0, 'rejected': 1}
    assert counts['SECURITY_ALERT2']['rejected'] == 5


@pytest.mark.parametrize('severity,status,route,output', [
    (None, 'OPEN', 'default', 'OPEN'), ('', '', 'default', ''),
    (' HIGH ', None, 'critical', None), ('HIGH', 'OPEN', 'critical', 'ESCALATED'),
    ('HIGH', 'ACK', 'critical', 'ACK'), ('CRITICAL', 'RESOLVED', 'critical', 'RESOLVED'),
    ('low', 'open', 'standard', 'OPEN'), ('\tHIGH\t', 'OPEN', 'default', 'OPEN'),
])
def test_null_empty_ascii_trim_and_status(severity, status, route, output):
    result = u.route_rows([[1, None, None, None, severity, status]])[0]
    assert result['route'] == route
    assert result['values'][5] == output


def test_bad_rendering_keeps_nulls_unpadded_and_timestamp():
    assert u.bad_line(0, [None, 4, None, datetime(2026, 11, 9), 'HIGH', 'ESCALATED']) == (
        '0,D,,D,4,D,,D,2026-11-09 00:00:00,D,HIGH,D,ESCALATED')
    assert u.bad_line(3, [1, None, None, None, '', None]) == '3,D,1,D,,D,,D,,D,,D,'
    assert u.bad_multiset(['x', 'x', 'y']) == {'x': 2, 'y': 1}


def snap(rows):
    return {'columns': ['ALERT_ID', 'STATUS_CD'],
            'types': {'ALERT_ID': ['bigint', None, 64, 0, None],
                      'STATUS_CD': ['character', 12, None, None, None]},
            'rows': [[cell(c) for c in r] for r in rows]}


def test_comparison_strict_strings_empty_and_multiplicity():
    a = snap([[1, 'OPEN        ']])
    assert u.comparisons(a, a, a, a)['passed']
    assert not u.comparisons(a, a, snap([[1, 'OPEN']]), a)['passed']
    assert not full_compare(snap([[1, None]]), snap([[1, '']]), ['ALERT_ID'])['equal']
    duplicate = snap([[1, 'x'], [1, 'x']])
    assert not u.comparisons(duplicate, duplicate, duplicate, duplicate)['passed']
    assert u.comparisons(snap([]), snap([]), snap([]), snap([]))['passed']
    result = u.comparisons(a, a, snap([[1, 'KEEP']]), snap([[1, 'KEEP']]), duplicate=True)
    assert result['passed']
    assert not result['oracle1_dbt1']['equal']
    assert not result['oracle2_dbt2']['equal']


def test_empty_and_malformed_psv(tmp_path):
    path = tmp_path / 'input.psv'
    path.write_text('')
    assert u.read_psv(path) == []
    path.write_text('1|2\n')
    with pytest.raises(ValueError, match='six columns'):
        u.read_psv(path)
    path.write_text('bad|2|3||HIGH|OPEN\n')
    with pytest.raises(ValueError):
        u.read_psv(path)


def test_scope_and_write_guard():
    with pytest.raises(ValueError):
        u.target('other')
    with pytest.raises(ValueError):
        u.landing('other')
    with pytest.raises(ValueError):
        u.fixture_write(None, [], 'INSERT INTO SFX_D1110_AFTER.PC_SRC.SECURITY_ALERT VALUES (1)')
    with pytest.raises(ValueError):
        u.fixture_write(None, [], 'GRANT SELECT ON ALL TABLES TO ROLE ANYONE')


def test_stats_per_instance():
    stats = u.parse_stats('''WRT_8036 Target: SECURITY_ALERT (Instance Name: [SECURITY_ALERT])
WRT_8038 Inserted rows - Requested: 2 Applied: 1 Rejected: 1 Affected: 1
WRT_8041 Updated rows - Requested: 3 Applied: 3 Rejected: 0 Affected: 3
WRT_8036 Target: SECURITY_ALERT (Instance Name: [SECURITY_ALERT2])
WRT_8038 Inserted rows - Requested: 0 Applied: 0 Rejected: 0 Affected: 0
WRT_8350 Rejected rows (DD_REJECT/not permitted) written to reject file: 5''')
    assert stats['SECURITY_ALERT']['inserted'] == 1
    assert stats['SECURITY_ALERT']['updated'] == 3
    assert stats['SECURITY_ALERT']['rejected'] == 1
    assert stats['SECURITY_ALERT2']['rejected'] == 5


def test_macro_guard_and_reject_projection():
    from jinja2 import Environment
    macro = (u.ROOT / 'warehouse/dbt/macros/pc_audit_security_alert.sql').read_text()
    module = Environment().from_string(macro).module
    sql = module.pc_audit_security_alert('MY_SOURCE')
    assert 'count(*) over (partition by ROUTE,ALERT_ID)' in sql
    assert 'max(ROUTE_COUNT) over ()' in sql
    assert '1 / iff(MAX_ROUTE_COUNT>1,0,1) = 1' in sql
    assert 'order by ROUTE desc' in sql
    assert 'rpad(STATUS_CD,12' in sql
    rejects = module.pc_audit_security_alert('MY_SOURCE', rejects=True)
    assert 'ROUTE=3 or ALERT_ID is null' in rejects
    assert 'rpad(' not in rejects
    assert 'as ROW_TYPE' in rejects
