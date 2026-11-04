import hashlib
import re
from pathlib import Path

import sf_attribution as attr

MIGRATIONS = Path(__file__).resolve().parents[2] / 'snowflake/pipeline_migrations'


def test_ops_migration_renders_only_known_jinja_variables():
    names = attr.names(['doc_usage_dashboard'])
    migration = MIGRATIONS / 'doc_usage_dashboard/V1.9.0__ops_freshness_fault_switch.sql'
    sql = migration.read_text()
    variables = set(re.findall(r'{{\s*(\w+)\s*}}', sql))
    assert variables <= names.keys()
    rendered = re.sub(r'{{\s*(\w+)\s*}}', lambda match: names[match[1]], sql)
    assert '{{' not in rendered


def test_ops_runtime_role_migration_renders_with_attributed_names():
    names = attr.names(['doc_usage_dashboard'])
    migration = MIGRATIONS / 'doc_usage_dashboard/V1.10.0__ops_runtime_role.sql'
    sql = migration.read_text()
    variables = set(re.findall(r'{{\s*(\w+)\s*}}', sql))
    assert variables <= names.keys()
    rendered = re.sub(r'{{\s*(\w+)\s*}}', lambda match: names[match[1]], sql)
    assert 'CREATE ROLE IF NOT EXISTS SFNFR_20261104_OPS_DOC_USAGE_DASHBOARD' in rendered
    assert 'GRANT ROLE SFNFR_20261104_OPS_DOC_USAGE_DASHBOARD TO USER SFNFR_20261104_SVC_CS_DOC_USAGE_DASHBOARD_ACCOUNT_USAGE' in rendered
    assert 'GRANT ROLE SFNFR_20261104_OPS_DOC_USAGE_DASHBOARD TO ROLE SFNFR_20261104_BUILDER' in rendered
    for grant in (
        'GRANT USAGE ON DATABASE SFNFR_20261104_DB_DOC_USAGE_DASHBOARD',
        'GRANT USAGE ON SCHEMA SFNFR_20261104_DB_DOC_USAGE_DASHBOARD.OPS',
        'GRANT USAGE ON SCHEMA SFNFR_20261104_DB_DOC_USAGE_DASHBOARD.ANALYTICS',
        'GRANT USAGE, MONITOR ON WAREHOUSE SFNFR_20261104_WH_DOC_USAGE_DASHBOARD',
        'GRANT SELECT ON VIEW SFNFR_20261104_DB_DOC_USAGE_DASHBOARD.OPS.WORKLOAD_FRESHNESS',
        'GRANT SELECT ON TABLE SFNFR_20261104_DB_DOC_USAGE_DASHBOARD.OPS.REFRESH_LOG',
        'GRANT SELECT ON TABLE SFNFR_20261104_DB_DOC_USAGE_DASHBOARD.OPS.REFRESH_TABLES',
        'GRANT SELECT ON TABLE SFNFR_20261104_DB_DOC_USAGE_DASHBOARD.OPS.FAULT_SWITCH',
        'GRANT UPDATE ON TABLE SFNFR_20261104_DB_DOC_USAGE_DASHBOARD.OPS.FAULT_SWITCH',
        'GRANT OPERATE, MONITOR ON TASK SFNFR_20261104_DB_DOC_USAGE_DASHBOARD.ANALYTICS.REFRESH_DOC_USAGE_DASHBOARD',
    ):
        assert grant in rendered
    assert '{{' not in rendered


def test_pipeline_migrations_do_not_change_masking_policies():
    for path in MIGRATIONS.rglob('*.sql'):
        sql = path.read_text().upper()
        assert 'MASKING POLICY' not in sql
        assert 'IS_ROLE_IN_SESSION' not in sql


def test_unmerged_history_alignment_matches_rendered_landing_migration():
    names = attr.names(['doc_usage_dashboard', 'doc_search_api', 'churn_model'])
    folder = MIGRATIONS / 'doc_usage_dashboard'
    sql = (folder / 'V1.8.0__postgres_landing.sql').read_text()
    rendered = re.sub(r'{{\s*(\w+)\s*}}', lambda match: names[match[1]], sql).strip().removesuffix(';')
    checksum = hashlib.sha224(rendered.encode()).hexdigest()
    repair = (folder / 'V1.8.1__align_unmerged_landing_history.sql').read_text()
    assert f"SET CHECKSUM = '{checksum}'" in repair
    assert "AND CHECKSUM = '7b2b476254f5d25af10dac8749372fb6adcb7d688a369e8e3e1708ea'" in repair
