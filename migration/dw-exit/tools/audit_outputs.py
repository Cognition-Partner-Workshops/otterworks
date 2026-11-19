"""Declared audit evidence relations, independent of execution dependencies."""
PC_TABLES = ('STG_AUDIT_EVENT', 'AUDIT_EVENT', 'AUDIT_DAILY_SUMMARY', 'SECURITY_ALERT')


def outputs(obj):
    if obj['subject_area'] != 'audit' or obj['target_type'] == 'retire' or obj['system'] == 'spark':
        return obj.get('output_relations', [])
    if obj['system'] == 'powercenter':
        tables = PC_TABLES if obj['kind'] == 'workflow' else (obj['name'].upper().split('M_SFX_', 1)[1],)
        return ['SFX_AUDIT_PC.' + table for table in tables]
    if obj['name'] == '10_summary_daily':
        return ['SFX_AUDIT.AUDIT_DAILY_SUMMARY']
    if obj['name'] == 'SFX_AUDIT.M_RECON_TOTALS':
        return ['SFX_AUDIT.M_RECON_TOTALS_OUTPUT']
    return obj.get('output_relations', [])
