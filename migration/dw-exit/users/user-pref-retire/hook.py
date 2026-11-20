"""Retirement is not measurable target parity."""

OUTPUTS = {
    'USERS.USER_PREF': 'DROP TABLE IF EXISTS "USERS"."USER_PREF"',
    'USERS.STG_USER_PREF': 'DROP TABLE IF EXISTS "USERS"."STG_USER_PREF"',
    'USERS.V_USER_SETTINGS': 'DROP TABLE IF EXISTS "USERS"."V_USER_SETTINGS"',
}
REASON = ('retired (manifest target_type retire, target NONE); no target relation to '
          'measure — retirement evidence in retirement.json')


def materialize(before, after, ready, errors):
    for name, statement in OUTPUTS.items():
        ready.discard(name)
        after.execute(statement)
        errors[name] = REASON
