"""Execute documents proof legs and expose their measured object contracts."""
import json
from pathlib import Path

import duckdb

from parity import spark_documents
from parity.provenance import json_link

ROOT = Path(__file__).resolve().parents[3]
DIRECTORY = ROOT/'migration/dw-exit/documents'


def validated_history(path=DIRECTORY/'spark-replay.json'):
    replay = json.loads(path.read_text())
    if not replay['passed'] or len(set(replay['dates']))<2 or not all(s['measurement']['passed'] for s in replay['steps']):
        raise ValueError('Actual two-date replay has not passed')
    for field in ('landing_sha256','output_sha256','execution_log_sha256','conversion_sha256','legacy_code_sha256'):
        paths = [ROOT/name for name in replay[field]]
        if spark_documents.checksums(paths)!=replay[field]:
            raise ValueError('Stale binary history evidence: '+field)
    runtime = ROOT/'etl/spark/.data'/replay['namespace']
    actual = {str(p.relative_to(ROOT)) for p in (runtime/'lake/documents/file_object_binary_extract').rglob('*.parquet')}
    if actual!=set(replay['output_sha256']):
        raise ValueError('Binary history partitions changed since replay')
    return replay


def measure(manifest, namespace, business_date):
    from documents.prove_local import prove
    evidence = prove(ROOT/'migration/dw-exit/.runs/documents-pre-pc',ROOT/'warehouse/landing',namespace,business_date)
    with duckdb.connect() as before,duckdb.connect() as after:
        ready,errors,jobs = spark_documents.materialize(before,after,manifest['objects'],namespace)
    try:
        replay = validated_history()
    except (ValueError,OSError) as error:
        replay = {'passed':False,'error':str(error)}
        jobs['file_object_binary_extract']['status'] = 'red'
        jobs['file_object_binary_extract']['error'] = str(error)
    evidence['spark'] = {'namespace':namespace,'target':'duckdb','snowflake':'not attempted',
                         'jobs':jobs,'errors':errors,'ready':sorted(ready),'binary_history':replay,
                         'shared_tables':{'SFX_AUDIT.SECURITY_ALERT':{'manifest_subject':'audit','spark_subject':'documents'},
                                          'SFX_AUDIT.SPARK_ALERT_ANOMALY':{'manifest_subject':None,'producer_area':'audit','spark_subject':'documents'}}}
    (DIRECTORY/'evidence.json').write_text(json.dumps(evidence,indent=2,default=str)+'\n')
    return evidence


def object_measurements(manifest, evidence):
    objects = {r['name']:r for r in evidence.get('objects',[])}
    results = {}
    evidence_path = Path('migration/dw-exit/documents/evidence.json')
    for obj in manifest['objects']:
        if obj['subject_area']!='documents':
            continue
        name = obj['name']
        if obj['target_type']=='retire':
            results[name] = {'status':'retired','reason':'Manifest retire candidate; DBQL evidence retained; not deletion approval','measurements':{}}
            continue
        measured,locations = {},{}
        if obj['system']=='spark':
            result = evidence['spark']['jobs'][name]
            if 'measurement' in result:
                measured['SFX_SPARK.'+name.upper()] = result['measurement']
                locations['SFX_SPARK.'+name.upper()] = ['spark','jobs',name,'measurement']
            for relation,side in result.get('side_outputs',{}).items():
                measured[relation] = side['measurement']
                locations[relation] = ['spark','jobs',name,'side_outputs',relation,'measurement']
            if name=='file_object_binary_extract' and evidence['spark']['binary_history'].get('passed'):
                measured['SFX_SPARK.'+name.upper()] = evidence['spark']['binary_history']['steps'][-1]['measurement']
                locations['SFX_SPARK.'+name.upper()] = ['spark','binary_history']
            status = result['status']
            reason = result.get('error') or ('; '.join(result.get('blockers',[])) or None)
        else:
            result = objects[name]
            group = ('shared_billing_with_candidate_storage' if name=='10_storage_monthly' else
                     'pc_relations' if obj['system']=='powercenter' else 'tpt_relations' if obj['kind']=='tpt' else 'sql_relations')
            for relation in result['relations']:
                measured[relation] = evidence[group][relation]
                locations[relation] = [group,relation]
            status = result['status']
            reason = '; '.join(result['blockers']) or ('measured parity mismatch' if status=='red' else None)
        results[name] = {'status':status,'reason':reason,'measurements':measured,
                         'decisions':evidence.get('decisions',[]) if not result.get('blockers') else [],
                         'metric_evidence':{relation:json_link(evidence_path,keys) for relation,keys in locations.items()}}
    return results
