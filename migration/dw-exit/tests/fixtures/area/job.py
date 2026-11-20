def run(session):
    return session.table('STG_T').select('ID', 'VALUE')
