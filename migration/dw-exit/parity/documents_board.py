"""Build the sfg1120 documents slice of the local DuckDB parity board."""
import argparse
from collections import Counter
import inspect
import json
from pathlib import Path
import sys

import duckdb
import yaml

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT/'migration/dw-exit'), str(ROOT/'migration/dw-exit/tools')]

from documents.prove_local import prove
from parity import documents_retirement, ladder, spark_documents
from warehouse.run_config import RunConfig


DIRECTORY = ROOT/'migration/dw-exit/documents'
EVIDENCE = DIRECTORY/'evidence.json'
BRANCH = 'devin/sfg1120-documents'
REPOSITORY = 'https://github.com/Cognition-Partner-Workshops/otterworks'
SNOWFLAKE_REASON = 'Snowflake login unavailable; no connection or object creation attempted.'
METRICS = {'row_count': ladder.local_measure, 'column_profile': ladder.local_measure,
           'keyed_row_hash': ladder.local_compare, 'sampled_differences': ladder.local_compare}


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, default=str)+'\n')


def link(path, start=None, end=None, ref=BRANCH):
    path = Path(path)
    if path.is_absolute():
        path = path.relative_to(ROOT)
    suffix = f'#L{start}-L{end or start}' if start else ''
    return {'file': str(path), 'start_line': start, 'end_line': end or start,
            'url': f'{REPOSITORY}/blob/{ref}/{path}{suffix}'}


def code_link(function):
    lines, start = inspect.getsourcelines(function)
    return link(inspect.getsourcefile(function), start, start+len(lines)-1)


def evidence_link(path, value):
    if not value:
        return link(path)
    text = path.read_text()
    # Exact indentation and JSON value delimit the top-level evidence group.
    prefix = f'  {json.dumps(value)}: '
    start = text.index('\n'+prefix)+1
    offset = start+len(prefix)
    _, length = json.JSONDecoder().raw_decode(text[offset:])
    return link(path,text.count('\n',0,start)+1,text.count('\n',0,offset+length)+1)


def validated_history(path=DIRECTORY/'spark-replay.json'):
    replay = json.loads(path.read_text())
    if replay['namespace'] != RunConfig.from_env().before_namespace:
        raise ValueError('Binary history belongs to another run namespace')
    if (not replay['passed'] or len(set(replay['dates']))<2
            or not all(s['measurement']['passed'] for s in replay['steps'])):
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


def measure(objects, namespace, business_date, pre_pc):
    evidence = prove(pre_pc,ROOT/'warehouse/landing',namespace,business_date)
    with duckdb.connect() as before,duckdb.connect() as after:
        _,errors,jobs = spark_documents.materialize(before,after,objects,namespace)
    try:
        replay = validated_history()
    except (ValueError,OSError) as error:
        replay = {'passed':False,'error':str(error)}
        jobs['file_object_binary_extract']['status'] = 'red'
        jobs['file_object_binary_extract']['error'] = str(error)
    evidence['spark'] = {'jobs':jobs,'errors':errors,'binary_history':replay}
    evidence['retirement'] = documents_retirement.measure(objects)
    return evidence


def apply_deviation(item, measurements, decisions):
    if item['status'] != 'red' or item.get('reason'):
        return item
    failing = [measurement for measurement in measurements.values() if not measurement['passed']]
    proofs = [measurement.get('owner_decision', {}) for measurement in failing]
    approvals = {d['decision_id']:d for d in decisions
                 if 'decision_id' in d and d['status'] in ('approved','approved-pending-confirmation')}
    if proofs and all(p.get('decision_id') in approvals and p.get('scope_valid')
                      and p['approved_comparison']['passed'] for p in proofs):
        entries = [approvals[p['decision_id']] for p in proofs]
        pending = [entry['confirmation'] for entry in entries if entry['status']=='approved-pending-confirmation']
        status = 'amber' if pending else 'approved_deviation'
        item.update(status=status,local_duckdb=status,measurement_status='red',
                    reason='; '.join(dict.fromkeys(pending or [d['new_behaviour'] for d in entries])),
                    owner_decision_evidence=proofs)
    return item


def object_measurements(objects, evidence):
    sql = {r['name']:r for r in evidence['objects']}
    results = {}
    for obj in objects:
        name = obj['name']
        item = {'status':'red','reason':None,'measurements':{},'group':None}
        results[name] = item
        if obj['target_type']=='retire':
            retire = evidence['retirement'][name]
            item.update(status='retired',reason=retire['reason'],group='retirement',retirement=retire)
            continue
        if obj['system']=='spark':
            result = evidence['spark']['jobs'][name]
            if 'measurement' in result:
                item['measurements']['SFX_SPARK.'+name.upper()] = result['measurement']
            for relation,side in result.get('side_outputs',{}).items():
                item['measurements'][relation] = side['measurement']
            if name=='file_object_binary_extract' and evidence['spark']['binary_history'].get('passed'):
                item['measurements']['SFX_SPARK.'+name.upper()] = evidence['spark']['binary_history']['steps'][-1]['measurement']
            item.update(status=result['status'],reason=result.get('error') or '; '.join(result.get('blockers',[])) or None,
                        group='spark')
            continue
        result = sql[name]
        group = ('shared_billing_boundary' if name=='10_storage_monthly' else 'pc_sessions' if obj['kind']=='session' else
                 'pc_mappings' if obj['kind']=='mapping' else 'tpt_relations' if obj['kind']=='tpt' else 'sql_relations')
        measurements = {relation:evidence[group][relation] for relation in result['relations']}
        item.update(status=result['status'],reason='; '.join(result['blockers']) or None,group=group,measurements=measurements)
        apply_deviation(item,measurements,evidence['decisions'])
        if item['status']=='red' and not item['reason']:
            item['reason'] = 'Measured parity mismatch.' if measurements else 'No local measurements.'
        if item['status']=='green' and name=='SFX_DOCUMENTS.STORAGE_USAGE_DAILY':
            item.update(status='amber',reason='Exact duplicate removal matches Teradata; finance still needs to confirm invoice impact.')
    return results


def build_rows(objects, evidence, evidence_path=EVIDENCE):
    measured = object_measurements(objects,evidence)
    specs = {s['name']:s for path in ('objects.json','spark_jobs.json')
             for s in json.loads((DIRECTORY/path).read_text())}
    rows = []
    for obj in objects:
        item = measured[obj['name']]
        measurements = item['measurements']
        spec = specs.get(obj['name'],{})
        converted = [link(spec[k]) for k in ('conversion','producer','model') if k in spec]
        if obj['system']=='spark':
            converted.extend(link(p) for p in sorted((ROOT/spec['model']).parent.glob('*_jdbc.sql')))
        sources = [link(obj['source'])]
        retirement = item.get('retirement')
        if retirement:
            for query in retirement['baseline_queries']:
                sources.extend([link(documents_retirement.DBQL/'qrylog.csv',query['qrylog_line'],ref=retirement['baseline_commit']),
                                link(documents_retirement.DBQL/'objectusage.csv',query['objectusage_line'],ref=retirement['baseline_commit'])])
        row = {k:obj[k] for k in ('id','name','kind','wave','owner','subject_area','licence_dependency','target','target_type')}
        row.update(status=item['status'],local_duckdb=item['status'],reason=item['reason'],
                   migration_status=obj['status'],licence_dependency_count=int(obj['licence_dependency']!='none'),
                   snowflake='red',snowflake_reason=SNOWFLAKE_REASON,
                   row_count={side:sum(m['row_count'][side] for m in measurements.values())
                              for side in ('before','after')} if measurements else None,
                   relation_row_counts={relation:m['row_count'] for relation,m in measurements.items()} or None,
                   provenance={'source':sources,'converted':converted,'metrics':{k:code_link(fn) for k,fn in METRICS.items()}},
                   metric_evidence=evidence_link(evidence_path,item['group']))
        for metric in METRICS.keys()-{'row_count'}:
            row[metric] = {relation:m[metric] for relation,m in measurements.items()} or None
        for key in ('retirement','owner_decision_evidence','measurement_status'):
            if key in item:
                row[key] = item[key]
        rows.append(row)
    return rows


def markdown(rows, summary):
    labels = ('green','approved_deviation','amber','retired','red')
    text = ['# sfg1120 Documents — local DuckDB parity board', '',
            ', '.join(f"{summary.get(key,0)} {key.replace('_',' ')}" for key in labels)+'. **Snowflake: red.** '+SNOWFLAKE_REASON,
            '', 'Each metric links to its calculation; evidence includes per-relation profiles, SHA-256s and all fixture differences.',
            '', '| Object | Local DuckDB | Snowflake | Rows (old → new) | Columns profiled | Hash delta | Differing keys | Evidence |',
            '|---|---|---|---:|---:|---:|---:|---|']
    def anchor(label, location):
        return f"[{label}]({location['url']})"
    for row in rows:
        m = row['provenance']['metrics']
        counts = row['row_count']
        values = ['—']*4
        if counts:
            values = [
                anchor(f"{counts['before']} → {counts['after']}",m['row_count']),
                anchor(sum(len(r['before']) for r in row['column_profile'].values()),m['column_profile']),
                anchor(sum(r['difference'] for r in row['keyed_row_hash'].values()),m['keyed_row_hash']),
                anchor(sum(len(r) for r in row['sampled_differences'].values()),m['sampled_differences']),
            ]
        legacy = anchor(row['name'],row['provenance']['source'][0])
        new = row['provenance']['converted']
        evidence = [anchor('Measurements',row['metric_evidence'])]
        if new:
            evidence.append(anchor('Conversion',new[0]))
        if row.get('retirement'):
            count = row['retirement']['baseline_reads']
            evidence = [anchor(f'DBQL: {count} reads',row['metric_evidence'])]
            evidence += [anchor('Query',s) for s in row['provenance']['source'][1::2]]
        text.append('| '+' | '.join([legacy,row['status'].replace('_',' '),'red',*values,', '.join(evidence)])+' |')
    return '\n'.join(text)+'\n'


def main():
    parser = argparse.ArgumentParser()
    config = RunConfig.from_env()
    parser.add_argument('--pre-pc',type=Path,default=DIRECTORY.parent/'.runs'/f'documents-{config.token}-pre-pc')
    parser.add_argument('--namespace',default=config.before_namespace)
    parser.add_argument('--business-date',default='20261109')
    args = parser.parse_args()
    manifest = yaml.safe_load((DIRECTORY.parent/'manifest.yaml').read_text())
    objects = [o for o in manifest['objects'] if o['subject_area']=='documents']
    evidence = measure(objects,args.namespace,args.business_date,args.pre_pc)
    dump(EVIDENCE,evidence)
    rows = build_rows(objects,evidence)
    summary = dict(Counter(row['status'] for row in rows))
    dump(DIRECTORY/'board.json',{'subject_area':'documents','run_token':config.token,'target':'duckdb',
                               'snowflake':'red','snowflake_reason':SNOWFLAKE_REASON,'summary':summary,'rows':rows})
    (DIRECTORY/'board.md').write_text(markdown(rows,summary))
    print(json.dumps(summary,sort_keys=True))


if __name__ == '__main__':
    main()
