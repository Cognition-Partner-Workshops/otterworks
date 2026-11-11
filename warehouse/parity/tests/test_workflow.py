import pytest

from parity import workflow

ENABLED = ['s_m_SFX_STG_AUDIT_EVENT', 's_m_SFX_AUDIT_EVENT', 's_m_SFX_AUDIT_DAILY_SUMMARY', 's_m_SFX_SECURITY_ALERT']


def test_graph_matches_canonical_xml():
    tasks = workflow.graph()
    assert {n: t['after'] for n, t in tasks.items()} == {
        'Start': [],
        's_m_SFX_STG_AUDIT_EVENT': ['Start'],
        's_m_SFX_SECURITY_ALERT': ['Start'],
        's_m_SFX_AUDIT_EVENT': ['s_m_SFX_STG_AUDIT_EVENT'],
        's_m_SFX_AUDIT_DAILY_SUMMARY': ['s_m_SFX_AUDIT_EVENT'],
        's_m_SFX_AUDIT_EVENT_ARCHIVE': ['s_m_SFX_AUDIT_EVENT'],
    }
    assert sorted(n for n, t in tasks.items() if t['type'] == 'Session' and t['enabled']) == sorted(ENABLED)
    assert not tasks['s_m_SFX_AUDIT_EVENT_ARCHIVE']['enabled']


def test_selector_excludes_disabled_archive():
    models = workflow.selector(workflow.graph())
    assert 'pc_audit__audit_event_archive' not in models
    assert models.index('pc_audit__stg_audit_event') < models.index('pc_audit__audit_event') \
        < models.index('pc_audit__audit_daily_summary')
    assert 'pc_audit__security_alert' in models


def test_success_runs_enabled_sessions_only():
    calls = []
    result = workflow.run(workflow.graph(), lambda s, m: calls.append(s) or 0)
    assert result['status'] == 'SUCCEEDED' and sorted(calls) == sorted(ENABLED)
    assert result['sessions']['s_m_SFX_AUDIT_EVENT_ARCHIVE'] == 'DISABLED'


@pytest.mark.parametrize('failed,skipped', [
    ('s_m_SFX_STG_AUDIT_EVENT', ['s_m_SFX_AUDIT_EVENT', 's_m_SFX_AUDIT_DAILY_SUMMARY']),
    ('s_m_SFX_AUDIT_EVENT', ['s_m_SFX_AUDIT_DAILY_SUMMARY']),
    ('s_m_SFX_AUDIT_DAILY_SUMMARY', []),
    ('s_m_SFX_SECURITY_ALERT', []),
])
def test_failure_blocks_downstream_and_success_stamp(failed, skipped):
    calls = []
    result = workflow.run(workflow.graph(), lambda s, m: calls.append(s) or (1 if s == failed else 0))
    assert result['status'] == 'FAILED'
    assert result['sessions'][failed] == 'FAILED'
    assert not set(skipped) & set(calls)
    assert all(result['sessions'][s] == 'NOTSTARTED' for s in skipped)
    independent = set(ENABLED) - {failed} - set(skipped)
    assert all(result['sessions'][s] == 'SUCCEEDED' for s in independent)


def test_dbt_command_scopes_schema_and_model():
    argv = workflow.dbt_command('pc_audit__audit_event', 'PC_FX_UNT9_AUDIT_WF')
    assert argv[1] == 'build' and argv[argv.index('--select') + 1] == 'pc_audit__audit_event'
    assert '"pc_audit_schema": "PC_FX_UNT9_AUDIT_WF"' in argv[-1]
    assert '--full-refresh' not in argv


def test_cli_rejects_unknown_schema():
    with pytest.raises(SystemExit):
        workflow.main(['--schema', 'PC_CONTENT', '--step', 'x'])
