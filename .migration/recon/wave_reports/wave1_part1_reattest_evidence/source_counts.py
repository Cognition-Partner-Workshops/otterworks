import os, oracledb, psycopg, boto3
_d=os.environ["OW_BILLING_FIXTURE_DSN"].split("/",2); u,p,dsn=_d[0],_d[1],_d[2]
c=oracledb.connect(user=u,password=p,dsn=dsn); cur=c.cursor()
for q in ["select count(*) from customer_master where batch_no=85559852","select count(*) from customer_master","select count(*) from customer_master_hist","select count(*) from entity_attr_value where entity_type='CUSTOMER'","select count(*) from entity_attr_value","select sequence_name,last_number from user_sequences where sequence_name like 'SEQ_CUSTOMER%' or sequence_name like 'SEQ_ENTITY%'"]:
    try: cur.execute(q); print(q,"->",cur.fetchall())
    except Exception as e: print(q,"ERR",e)
pg=psycopg.connect(os.environ["OW_PG_DSN"]); pc=pg.cursor()
for q in ["select count(*) from otterworks_demo.documents","select count(*) from otterworks_demo.document_versions","select count(*) from otterworks_demo.document_snapshots","select count(*) from otterworks_demo.document_snapshots s where not exists (select 1 from otterworks_demo.documents d where d.id=s.document_id)"]:
    pc.execute(q); print(q,"->",pc.fetchall())
d=boto3.client("dynamodb",endpoint_url=os.environ["AWS_ENDPOINT_URL"],region_name="us-east-1",aws_access_key_id="test",aws_secret_access_key="test")
n=0; kw={}
while True:
    r=d.scan(TableName="otterworks-file-metadata",Select="COUNT",**kw); n+=r["Count"]
    if "LastEvaluatedKey" in r: kw={"ExclusiveStartKey":r["LastEvaluatedKey"]}
    else: break
print("dynamo items",n)
