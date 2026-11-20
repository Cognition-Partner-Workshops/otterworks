"""Retirement is not measurable target parity."""

OUTPUTS = ('USERS.USER_PREF', 'USERS.STG_USER_PREF', 'USERS.V_USER_SETTINGS')
REASON = ('retired (manifest target_type retire, target NONE); no target relation to '
          'measure — retirement evidence in retirement.json')


def materialize(before, after, ready, errors):
    for name in OUTPUTS:
        ready.discard(name)
        after.execute('DROP TABLE IF EXISTS ' + '.'.join('"' + p + '"' for p in name.split('.')))
        errors[name] = REASON
