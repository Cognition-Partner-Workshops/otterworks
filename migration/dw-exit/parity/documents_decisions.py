"""Independent, exhaustive scope proof for current-version owner decisions."""
from collections import Counter

from .ladder import canonical, local_compare


def version_scope(before, after, measurements):
    before.execute('CREATE SCHEMA APPROVED_DOCUMENTS')
    before.execute('''CREATE TABLE APPROVED_DOCUMENTS.LATEST AS
        SELECT * EXCLUDE (timestamp_rank) FROM (
            SELECT *, DENSE_RANK() OVER (
                PARTITION BY DOCUMENT_ID ORDER BY VERSION_TS DESC) timestamp_rank
            FROM SFX_DOCUMENTS.STG_DOC_VERSION) WHERE timestamp_rank=1''')
    tied = [r[0] for r in before.execute('''SELECT DOCUMENT_ID
        FROM APPROVED_DOCUMENTS.LATEST GROUP BY DOCUMENT_ID HAVING COUNT(*)>1
        ORDER BY DOCUMENT_ID''').fetchall()]
    scope = set(tied)
    latest = before.execute('SELECT * FROM APPROVED_DOCUMENTS.LATEST').fetchall()
    legacy = before.execute('SELECT * FROM SFX_DOCUMENTS.DOC_VERSION').fetchall()
    eligible = Counter(canonical(row) for row in latest)
    valid = all(eligible[canonical(row)] for row in legacy if row[1] in scope)
    valid &= Counter(row[1] for row in legacy if row[1] in scope) == Counter(tied)
    before.execute('''CREATE TABLE APPROVED_DOCUMENTS.DOC_VERSION AS
        SELECT * FROM SFX_DOCUMENTS.DOC_VERSION WHERE DOCUMENT_ID NOT IN
            (SELECT DOCUMENT_ID FROM APPROVED_DOCUMENTS.LATEST
             GROUP BY DOCUMENT_ID HAVING COUNT(*)>1)
        UNION ALL
        SELECT l.* FROM APPROVED_DOCUMENTS.LATEST l
        WHERE l.DOCUMENT_ID IN (SELECT DOCUMENT_ID FROM APPROVED_DOCUMENTS.LATEST
            GROUP BY DOCUMENT_ID HAVING COUNT(*)>1)
        AND l.VERSION_NO=(SELECT MAX(x.VERSION_NO) FROM APPROVED_DOCUMENTS.LATEST x
            WHERE x.DOCUMENT_ID=l.DOCUMENT_ID)''')
    before.execute('''CREATE VIEW APPROVED_DOCUMENTS.V_DOCUMENT_VERSIONS AS
        SELECT d.DOCUMENT_ID,d.OWNER_USER_ID,v.VERSION_ID,v.VERSION_TS,v.FILE_SIZE
        FROM SFX_DOCUMENTS.DOCUMENT d JOIN APPROVED_DOCUMENTS.DOC_VERSION v
        ON d.DOCUMENT_ID=v.DOCUMENT_ID''')
    before.execute('''CREATE VIEW APPROVED_DOCUMENTS.V_WORKSPACE_STORAGE AS
        SELECT OWNER_USER_ID,COUNT(*) DOCUMENT_COUNT,
            CAST(SUM(FILE_SIZE) AS DECIMAL(38,0)) TOTAL_BYTES
        FROM APPROVED_DOCUMENTS.V_DOCUMENT_VERSIONS GROUP BY OWNER_USER_ID''')
    owners = {owner for doc,owner in before.execute(
        'SELECT DOCUMENT_ID,OWNER_USER_ID FROM SFX_DOCUMENTS.DOCUMENT').fetchall() if doc in scope}
    for name, index, allowed in (('DOC_VERSION',1,scope),
                                  ('V_DOCUMENT_VERSIONS',0,scope),
                                  ('V_WORKSPACE_STORAGE',0,owners)):
        source, target = 'SFX_DOCUMENTS.'+name, 'DOCUMENTS.'+name
        # Relations are assembled only from the fixed three-relation decision-proof tuple above, never row data.
        # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
        old = before.execute('SELECT * FROM '+source).fetchall()
        # Relations are assembled only from the fixed three-relation decision-proof tuple above, never row data.
        # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
        new = after.execute('SELECT * FROM '+target).fetchall()
        old_counts = Counter(canonical(row) for row in old)
        new_counts = Counter(canonical(row) for row in new)
        old_delta, new_delta = old_counts-new_counts, new_counts-old_counts
        old_keys = {canonical(row):row[index] for row in old}
        new_keys = {canonical(row):row[index] for row in new}
        outside = sum(count for row,count in old_delta.items()
                      if old_keys[row] not in allowed)
        outside += sum(count for row,count in new_delta.items()
                       if new_keys[row] not in allowed)
        approved = local_compare(before,after,'APPROVED_DOCUMENTS.'+name,target,
                                 sample_size=10000)
        measurements[name]['owner_decision'] = dict(
            decision_id='documents-latest-version', scope_valid=bool(valid and outside==0),
            scope_document_ids=tied, scope_key_values=sorted(allowed),
            mismatching_key_values=sorted({old_keys[row] for row in old_delta} |
                                          {new_keys[row] for row in new_delta}),
            outside_scope_rows=outside, legacy_latest_winner_valid=bool(valid),
            mismatching_rows={'before':[dict(row=row,count=count) for row,count in sorted(old_delta.items())],
                              'after':[dict(row=row,count=count) for row,count in sorted(new_delta.items())]},
            approved_comparison=approved)
