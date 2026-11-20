"""Local parameter binding for the daily procedure's delete/insert transaction."""
import datetime as dt
import os


def materialize(before, after, ready, errors):
    target = 'USERS.USER_ACTIVITY_DAILY'
    if not {target, 'USERS.V_ACTIVITY_DAILY'} <= ready:
        ready.discard(target)
        errors[target] = 'daily procedure input not materialized'
        return
    try:
        day = dt.datetime.strptime(os.environ.get('BUSINESS_DATE', '20261109'), '%Y%m%d').date()
        after.execute('BEGIN TRANSACTION')
        after.execute('DELETE FROM USERS.USER_ACTIVITY_DAILY WHERE ACTIVITY_ID >= 10000000000')
        after.execute('INSERT INTO USERS.USER_ACTIVITY_DAILY SELECT * FROM USERS.V_ACTIVITY_DAILY '
                      'WHERE ACTIVITY_DT = ?', [day])
        after.execute('COMMIT')
    except Exception as error:
        try:
            after.execute('ROLLBACK')
        except Exception:
            pass
        ready.discard(target)
        errors[target] = 'daily procedure failed: ' + str(error).splitlines()[0]
