import ast
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from zipfile import ZIP_DEFLATED, ZipFile

import duckdb
import pytest
import yaml

from parity import spark_documents as documents
from parity.ladder import local_compare

ROOT = Path(__file__).resolve().parents[3]
SPECS = json.loads((documents.DOCUMENTS/'spark_jobs.json').read_text())


def spec(name):
    return next(row for row in SPECS if row['name']==name)


def fixture_runtime(tmp_path):
    landing = tmp_path/'landing/documents/DOC_TAG'
    output = tmp_path/'lake/documents/docs_tag_normalize'
    logs = tmp_path/'logs'
    for folder in (landing,output,logs):
        folder.mkdir(parents=True)
    source = landing/'20261109.psv'
    source.write_text('DOC_TAG_ID|DOCUMENT_ID|TAG\n1|1| A  B \n2|1|\n')
    parquet = output/'part-00000.parquet'
    with duckdb.connect() as c:
        c.execute("CREATE TABLE result AS SELECT 1::bigint DOC_TAG_ID,1::bigint DOCUMENT_ID,' A  B ' TAG,'a-b' NORMALIZED_TAG UNION ALL SELECT 2,1,NULL,''")
        c.execute("COPY result TO '"+str(parquet)+"' (FORMAT PARQUET)")
    log = logs/'docs_tag_normalize.log'
    log.write_text('Successfully stopped SparkContext\n')
    os.utime(source,ns=(1000000000,1000000000))
    for path in (parquet,log):
        os.utime(path,ns=(2000000000,2000000000))
    return source,parquet,log


def materialize_tag(runtime):
    objects = [{'name':'docs_tag_normalize','subject_area':'documents','system':'spark',
                'target':'spark__docs_tag_normalize','target_type':'dbt_model'}]
    with duckdb.connect() as before,duckdb.connect() as after:
        return documents.materialize(before,after,objects,'fixture',runtime=runtime)


def test_actual_output_fixture_and_landing_hash(tmp_path):
    source,parquet,_ = fixture_runtime(tmp_path)
    ready,errors,evidence = materialize_tag(tmp_path)
    assert not errors and ready=={'SPARK.SPARK__DOCS_TAG_NORMALIZE'}
    row = evidence['docs_tag_normalize']
    assert row['measurement']['passed'] and row['status']=='green'
    assert row['measurement']['row_count']=={'before':2,'after':2}
    assert row['landing_sha256'][str(source)]==hashlib.sha256(source.read_bytes()).hexdigest()
    assert row['output_sha256'][str(parquet)]==hashlib.sha256(parquet.read_bytes()).hexdigest()


@pytest.mark.parametrize('failure',['missing_output','missing_input','stale_output','failed_execution'])
def test_missing_stale_or_failed_output_is_red(tmp_path,failure):
    source,parquet,log = fixture_runtime(tmp_path)
    if failure=='missing_output':
        parquet.unlink()
    elif failure=='missing_input':
        source.unlink()
    elif failure=='stale_output':
        os.utime(source,ns=(3000000000,3000000000))
    else:
        log.write_text('Traceback (most recent call last)\nSuccessfully stopped SparkContext')
    ready,errors,evidence = materialize_tag(tmp_path)
    assert not ready and errors
    assert evidence['docs_tag_normalize']['status']=='red'
    assert 'measurement' not in evidence['docs_tag_normalize']


def test_nested_partition_is_recovered(tmp_path):
    source = tmp_path/'landing/documents/DOCUMENT'
    output = tmp_path/'lake/documents/docs_event_export_hourly/EXPORT_BUCKET=9999'
    logs = tmp_path/'logs'
    for folder in (source,output,logs):
        folder.mkdir(parents=True)
    (source/'20261109.psv').write_text('DOCUMENT_ID|OWNER_USER_ID|FOLDER_ID|TITLE|CREATED_AT|STATUS\n-1|1|1|Test|2026-11-09 00:00:00|active\n')
    with duckdb.connect() as c:
        c.execute("COPY (SELECT -1::bigint DOCUMENT_ID,1::bigint OWNER_USER_ID,1::bigint FOLDER_ID,'Test' TITLE,timestamp '2026-11-09' CREATED_AT,'active' STATUS) TO '"+str(output/'part.parquet')+"' (FORMAT PARQUET)")
    (logs/'docs_event_export_hourly.log').write_text('Successfully stopped SparkContext')
    job = spec('docs_event_export_hourly')
    objects = [{'name':job['name'],'system':'spark','subject_area':'documents','target':job['target'],'target_type':'dbt_model'}]
    with duckdb.connect() as before,duckdb.connect() as after:
        ready,errors,evidence = documents.materialize(before,after,objects,'fixture',runtime=tmp_path)
        assert not errors and ready
        assert evidence[job['name']]['measurement']['passed']
        assert after.execute('SELECT EXPORT_BUCKET FROM SPARK.SPARK__DOCS_EVENT_EXPORT_HOURLY').fetchone()==(9999,)


def test_compaction_rejects_stale_upstream(tmp_path):
    landing = tmp_path/'landing/documents/DOCUMENT'
    upstream = tmp_path/'lake/documents/docs_event_export_hourly'
    output = tmp_path/'lake/documents/lake_compaction_documents'
    logs = tmp_path/'logs'
    for folder in (landing,upstream,output,logs):
        folder.mkdir(parents=True)
    for path in (landing/'day.psv',upstream/'part.parquet',output/'part.parquet'):
        path.write_text('not read in a freshness check')
        os.utime(path,ns=(1000000000,1000000000))
    os.utime(upstream/'part.parquet',ns=(3000000000,3000000000))
    (logs/'lake_compaction_documents.log').write_text('Successfully stopped SparkContext')
    with pytest.raises(ValueError,match='predates'):
        documents.files_for_job(tmp_path,spec('lake_compaction_documents'))


def test_model_contract_matches_all_approved_manifest_targets():
    objects = [o for o in yaml.safe_load((ROOT/'migration/dw-exit/manifest.yaml').read_text())['objects']
               if o['system']=='spark' and o['subject_area']=='documents']
    assert len(objects)==len(SPECS)==13
    contract = {r['name']:r for r in json.loads((ROOT/'migration/dw-exit/parity/documents.json').read_text())}
    for obj in objects:
        job = spec(obj['name'])
        assert not obj['output_relations']
        assert job['target']==obj['target'] and job['target_type']==obj['target_type']=='dbt_model'
        assert contract[job['contract']]['keys']==job['keys']
        assert "alias='"+obj['target']+"'" in (ROOT/job['model']).read_text()
    assert 'SPARK_SECURITY_ALERT_ANOMALY_JDBC' in contract


def test_udf_bodies_are_extracted_not_reimplemented():
    functions = documents.shipped_udfs()
    for name,function in [('doc_version_diff_stats','similarity'),('docs_search_log_parse','parse_action'),('docs_tag_normalize','normalize')]:
        tree = ast.parse((ROOT/'etl/spark/jobs/py'/(name+'.py')).read_text())
        old = next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==function)
        old.decorator_list = []
        new = next(n for n in ast.parse(functions['DOCS_'+function.upper()]['body']).body
                   if isinstance(n,ast.FunctionDef) and n.name==function)
        assert ast.dump(old)==ast.dump(new)
    old = ast.parse((ROOT/'etl/spark/jobs/py/common/binary_documents.py').read_text())
    new = ast.parse(functions['DOCS_EXTRACT_DOCUMENT']['body'])
    for name in ('document_text','extract_document'):
        assert ast.dump(next(n for n in old.body if isinstance(n,ast.FunctionDef) and n.name==name))==ast.dump(next(n for n in new.body if isinstance(n,ast.FunctionDef) and n.name==name))


def test_udf_null_empty_error_and_binary_digest():
    functions = documents.shipped_udfs()
    assert functions['DOCS_NORMALIZE']['handler'](None)==''
    assert functions['DOCS_PARSE_ACTION']['handler'](None) is None
    assert functions['DOCS_SIMILARITY']['handler'](None,None)==1.0
    result = functions['DOCS_EXTRACT_DOCUMENT']['handler'](b'not a zip')
    assert result['PAGE_COUNT']==0 and result['MEDIA_TYPE']=='application/octet-stream'
    assert result['ERROR'] and result['SHA256']==hashlib.sha256(b'not a zip').hexdigest()


def test_binary_partition_history_and_explicit_date(tmp_path):
    path = ROOT/'etl/spark/jobs/py/file_object_binary_extract.py'
    tree = ast.parse(path.read_text())
    cleanup = next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='drop_unpartitioned')
    scope = {'Path':Path,'shutil':shutil}
    exec(compile(ast.Module(body=[cleanup],type_ignores=[]),str(path),'exec'),scope)
    (tmp_path/'run_date=2026-11-18').mkdir()
    (tmp_path/'run_date=2026-11-19').mkdir()
    (tmp_path/'legacy.parquet').write_text('old root output')
    scope['drop_unpartitioned'](tmp_path)
    assert sorted(p.name for p in tmp_path.iterdir())==['run_date=2026-11-18','run_date=2026-11-19']
    model = ROOT/spec('file_object_binary_extract')['model']
    with pytest.raises(ValueError,match='template'):
        documents.render_model(model)
    assert "'2026-11-19'" in documents.render_model(model,'2026-11-19')


def test_capped_folder_walk_preserves_zero_parent_truthiness():
    with duckdb.connect() as c:
        c.execute('CREATE SCHEMA SPARK_INPUT')
        c.execute('CREATE TABLE SPARK_INPUT.FOLDER (FOLDER_ID BIGINT,PARENT_FOLDER_ID BIGINT)')
        c.execute('INSERT INTO SPARK_INPUT.FOLDER VALUES (0,NULL),(1,0),(2,1)')
        query = documents.render_model(ROOT/spec('docs_folder_tree_walk')['model'])
        assert sorted(c.execute(query).fetchall())==[(0,0,0),(1,1,20),(2,1,20)]


def test_graph_root_hop_cap_cycles_and_null_key():
    with duckdb.connect() as c:
        c.execute('CREATE SCHEMA SPARK_INPUT')
        c.execute('CREATE TABLE SPARK_INPUT.DOC_SHARE (OWNER_USER_ID BIGINT,SHARED_WITH_USER_ID BIGINT)')
        c.execute('INSERT INTO SPARK_INPUT.DOC_SHARE VALUES (1,2),(2,1),(2,NULL),(NULL,3),(3,4),(4,5)')
        query = documents.render_model(ROOT/spec('doc_share_graph_reach')['model'])
        assert dict(c.execute(query).fetchall())=={1:0,2:1,None:2,3:3,4:4}


def test_session_gap_is_strictly_greater_than_1800_seconds():
    with duckdb.connect() as c:
        c.execute('CREATE SCHEMA SPARK_INPUT')
        c.execute('CREATE TABLE SPARK_INPUT.COLLAB_SESSION (USER_ID BIGINT,DOCUMENT_ID BIGINT,EVENT_AT TIMESTAMP)')
        c.execute("INSERT INTO SPARK_INPUT.COLLAB_SESSION VALUES (1,1,'2026-11-09 00:00:00'),(1,1,'2026-11-09 00:30:00'),(1,1,'2026-11-09 01:00:00.000001')")
        rows = c.execute(documents.render_model(ROOT/spec('collab_session_sessionize')['model'])).fetchall()
        assert len(rows)==2 and sorted(r[2] for r in rows)==[1,2]


def test_composite_keys_preserve_multiplicity_and_default_hashes():
    with duckdb.connect() as before,duckdb.connect() as after:
        for c in (before,after):
            c.execute('CREATE SCHEMA TEST')
            c.execute("CREATE TABLE TEST.T AS SELECT 1 ID,'a' KIND,2 PAYLOAD UNION ALL SELECT 1,'b',3")
        default = local_compare(before,after,'TEST.T','TEST.T')
        explicit = local_compare(before,after,'TEST.T','TEST.T',keys=['ID'])
        assert default['keyed_row_hash']['before']==explicit['keyed_row_hash']['before']
        after.execute("INSERT INTO TEST.T VALUES (1,'b',3)")
        result = local_compare(before,after,'TEST.T','TEST.T',keys=['ID','KIND'])
        assert result['keyed_row_hash']['difference']==1
        assert result['sampled_differences'][0]['key']==[1,'b']
        with pytest.raises(ValueError,match='keys'):
            local_compare(before,after,'TEST.T','TEST.T',keys=['MISSING'])


@pytest.mark.parametrize('entrypoint',['repack','initialize'])
def test_packaged_binary_helper_imports_without_checkout(tmp_path,entrypoint):
    source = ROOT/'etl/spark/jobs/py/common'
    common = tmp_path/'etl/spark/jobs/py/common'
    shutil.copytree(source,common,ignore=shutil.ignore_patterns('__pycache__'))
    (tmp_path/'warehouse').mkdir()
    shutil.copy2(ROOT/'warehouse/run_config.py',tmp_path/'warehouse/run_config.py')
    if entrypoint=='repack':
        subprocess.run([sys.executable,str(common/'package.py')],cwd=tmp_path,
                       env={**os.environ,'NS':'package-test'},check=True,capture_output=True)
    else:
        path = ROOT/'etl/spark/fixture/initialize.py'
        tree = ast.parse(path.read_text())
        main = next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main')
        block = next(n for n in main.body if isinstance(n,ast.With))
        cache = tmp_path/'etl/spark/.cache/package-test'
        cache.mkdir(parents=True)
        exec(compile(ast.Module(body=[block],type_ignores=[]),str(path),'exec'),
             {'ROOT':tmp_path/'etl/spark','cache':cache,'ZipFile':ZipFile,'ZIP_DEFLATED':ZIP_DEFLATED})
    archive = tmp_path/'etl/spark/.cache/package-test/common.zip'
    result = subprocess.run([sys.executable,'-I','-c',
        "import sys;sys.path.insert(0,sys.argv[1]);from common.binary_documents import extract_document;print(extract_document(b'%PDF-1.4 /Type /Page (Hello) Tj')[0])",str(archive)],
        cwd=tmp_path,check=True,text=True,capture_output=True)
    assert result.stdout.strip()=='application/pdf'
