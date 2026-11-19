"""Declared audit evidence relations, independent of execution dependencies."""
PC_TABLES = ('STG_AUDIT_EVENT', 'AUDIT_EVENT', 'AUDIT_DAILY_SUMMARY', 'SECURITY_ALERT')
SPARK_JDBC = {'audit_daily_summary': 'sfx_audit.SPARK_AUDIT_SUMMARY',
              'compliance_flag_rules': 'sfx_audit.SPARK_COMPLIANCE_REVIEW'}
SPARK_JOBS = ('audit_actor_activity_join', 'audit_archive_resort', 'audit_daily_summary',
              'compliance_flag_rules', 'lake_compaction_audit')


def artifacts(obj):
    if obj['system'] != 'spark' or obj['name'] not in SPARK_JOBS:
        return []
    name = obj['name']
    return ['lake/audit/' + name] + (['jdbc:' + SPARK_JDBC[name]] if name in SPARK_JDBC else [])


def outputs(obj):
    if obj['subject_area'] != 'audit' or obj['target_type'] == 'retire':
        return obj.get('output_relations', [])
    if obj['system'] == 'spark':
        name = obj['name']
        return ['SFX_SPARK.' + name.upper()] + (['SFX_SPARK.' + name.upper() + '_JDBC'] if name in SPARK_JDBC else [])
    if obj['system'] == 'powercenter':
        tables = PC_TABLES if obj['kind'] == 'workflow' else (obj['name'].upper().split('M_SFX_', 1)[1],)
        return ['SFX_AUDIT_PC.' + table for table in tables]
    if obj['name'] == '10_summary_daily':
        return ['SFX_AUDIT.AUDIT_DAILY_SUMMARY']
    if obj['name'] == 'SFX_AUDIT.M_RECON_TOTALS':
        return ['SFX_AUDIT.M_RECON_TOTALS_OUTPUT']
    return obj.get('output_relations', [])
