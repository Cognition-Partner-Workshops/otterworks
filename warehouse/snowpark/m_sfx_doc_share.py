"""Publish the existing pc_content__doc_share dbt result at the mapping target."""


def run(session):
    database = session.get_current_database()
    return session.sql(f'''MERGE INTO {database}.DOCUMENTS.DOC_SHARE t
        USING {database}.PC_CONTENT.DOC_SHARE s ON t.SHARE_ID=s.SHARE_ID
        WHEN MATCHED THEN UPDATE SET t.DOCUMENT_ID=s.DOCUMENT_ID, t.USER_ID=s.USER_ID, t.ACCESS_LEVEL=s.ACCESS_LEVEL, t.SHARED_DT=s.SHARED_DT
        WHEN NOT MATCHED THEN INSERT (SHARE_ID,DOCUMENT_ID,USER_ID,ACCESS_LEVEL,SHARED_DT)
        VALUES (s.SHARE_ID,s.DOCUMENT_ID,s.USER_ID,s.ACCESS_LEVEL,s.SHARED_DT)''').collect()
