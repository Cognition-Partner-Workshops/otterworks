"""Publish the existing pc_content__document dbt result at the mapping target."""

import re


def run(session):
    database = session.get_current_database()
    if not re.fullmatch(r'(?:[A-Z_][A-Z_0-9]*|"[A-Z_][A-Z_0-9]*")', database):
        raise ValueError('Unexpected run database identifier')
    # Only the validated database identifier is interpolated.
    # nosemgrep: python.lang.security.audit.formatted-sql-query.formatted-sql-query, python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
    return session.sql(f'''MERGE INTO {database}.DOCUMENTS.DOCUMENT t
        USING {database}.PC_CONTENT.DOCUMENT s ON t.DOCUMENT_ID=s.DOCUMENT_ID
        WHEN MATCHED THEN UPDATE SET FOLDER_ID=s.FOLDER_ID, OWNER_USER_ID=s.OWNER_USER_ID, CUSTOMER_ID=s.CUSTOMER_ID, DOCUMENT_NAME=s.DOCUMENT_NAME, CREATED_DT=s.CREATED_DT, STATUS_CD=s.STATUS_CD, FILE_TYPE=s.FILE_TYPE
        WHEN NOT MATCHED THEN INSERT (DOCUMENT_ID,FOLDER_ID,OWNER_USER_ID,CUSTOMER_ID,DOCUMENT_NAME,CREATED_DT,STATUS_CD,FILE_TYPE)
        VALUES (s.DOCUMENT_ID,s.FOLDER_ID,s.OWNER_USER_ID,s.CUSTOMER_ID,s.DOCUMENT_NAME,s.CREATED_DT,s.STATUS_CD,s.FILE_TYPE)''').collect()
