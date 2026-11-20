"""Publish the existing pc_content__doc_share dbt result at the mapping target."""

import re


def run(session):
    database = session.get_current_database()
    if not re.fullmatch(r'(?:[A-Z_][A-Z_0-9]*|"[A-Z_][A-Z_0-9]*")', database):
        raise ValueError('Unexpected run database identifier')
    # Only the validated database identifier is interpolated.
    # nosemgrep: python.lang.security.audit.formatted-sql-query.formatted-sql-query, python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
    return session.sql(f'''MERGE INTO {database}.DOCUMENTS.DOC_SHARE t
        USING {database}.PC_CONTENT.DOC_SHARE s ON t.SHARE_ID=s.SHARE_ID
        WHEN MATCHED THEN UPDATE SET DOCUMENT_ID=s.DOCUMENT_ID, USER_ID=s.USER_ID, ACCESS_LEVEL=s.ACCESS_LEVEL, SHARED_DT=s.SHARED_DT
        WHEN NOT MATCHED THEN INSERT (SHARE_ID,DOCUMENT_ID,USER_ID,ACCESS_LEVEL,SHARED_DT)
        VALUES (s.SHARE_ID,s.DOCUMENT_ID,s.USER_ID,s.ACCESS_LEVEL,s.SHARED_DT)''').collect()
