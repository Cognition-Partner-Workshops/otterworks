"""Execute unchanged legacy scripts and native tasks against identical fakes."""

import argparse
import configparser
import copy
import csv
import hashlib
import importlib.util
import io
import json
import os
import sys
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from lakehouse.runtime import documents_external as native
from lakehouse.runtime.ingest import business_date
from lakehouse.runtime.layout import ROOT, data_root

from .documents_external_fakes import AWS, HTTP, Timer, frozen_datetime

OUTPUTS = ['search_documents', 'search_files', 'search_actions', 'cleanup_report', 'cleanup_actions']


def fixture(day):
    date = business_date(day).isoformat()
    instant = date + 'T04:00:00+00:00'
    documents = [{'document_id': i, 'title': f'Document {i}'} if i % 2 else {'id': i}
                 for i in range(1, 102)]
    documents[0].update(content='Unicode é | quoted', tags=['a', 'b'], owner_id=None)
    files = [{'file_id': i, 'file_name': f'File {i}'} if i % 2 else {'id': i, 'name': 'fallback', 'size': 9}
             for i in range(1, 102)]
    files[0].update(size_bytes=123, mime_type='text/plain', folder_id=7, tags=None)
    base = dict(documents=documents, files=files)
    search = [dict(name='normal_pagination', **base), dict(name='empty'),
              dict(name='queued', documents=[{'id': 1}], queued=True),
              dict(name='no_task_uid', files=[{'id': 1}], no_task_uid=True),
              dict(name='failed_tasks', documents=[{'id': 1}], task_status='failed'),
              dict(name='poll_timeout', documents=[{'id': 1}], never_complete=True),
              dict(name='bad_stats', bad_stats=True),
              dict(name='missing_secret', secret=' ')]
    search += [dict(name=kind, documents=[{'id': 1}], search_failure=kind)
               for kind in ['delete_http', 'create_http', 'settings_http', 'service_http', 'index_http']]
    objects = [dict(key=key, size=size, last_modified=instant, body='fixture content', metadata={'retain': 'yes'})
               for key, size in [('files/live', 17), ('files/orphan', 2147483648), ('files/empty', 0),
                                 ('files/copy-fail', 29), ('files/delete-fail', 31), ('outside/untouched', 5)]]
    references = [{'s3_key': 'files/live'}, {}, {'s3_key': ''}, {'s3_key': 'files/live'}]
    cleanup = [dict(name='normal_pagination', objects=objects, references=references),
               dict(name='empty'), dict(name='all_referenced', objects=objects[:1], references=references),
               dict(name='copy_delete_errors', objects=objects, references=references,
                    copy_failures=['files/copy-fail'], delete_failures=['files/delete-fail']),
               dict(name='list_error', list_error=True), dict(name='scan_error', scan_error=True),
               dict(name='report_error', objects=objects, references=references, report_error=True),
               dict(name='missing_owner', owner=''), dict(name='invalid_owner', owner='not-an-account')]
    return dict(version=1, business_date=day, instant=instant, search=search, cleanup=cleanup,
                config={'services': {'document_service_url': 'http://documents.fixture.invalid',
                                     'file_service_url': 'http://files.fixture.invalid',
                                     'meilisearch_url': 'http://search.fixture.invalid'},
                        'aws': {'region': 'us-east-1'},
                        's3': {'file_storage_bucket': 'fixture-source', 'quarantine_bucket': 'fixture-quarantine',
                               'data_lake_bucket': 'fixture-reports'}})


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def execute(side, job, scenario, document, config_path):
    http, aws, timer = HTTP(scenario), AWS(scenario), Timer()
    clock = frozen_datetime(document['instant'])
    env = dict(ETL_CONFIG_PATH=str(config_path), ETL_MEILISEARCH_API_KEY=scenario.get('secret', 'fixture-only-key'),
               ETL_S3_BUCKET_OWNER=scenario.get('owner', '123456789012'))
    output = io.StringIO()
    with patch.dict(os.environ, env), redirect_stdout(output):
        try:
            if side == 'legacy':
                directory = ROOT.parent / 'etl/scripts'
                config_module = load_module('runtime_config', directory / 'runtime_config.py')
                owner_module = load_module('bucket_owner', directory / 'bucket_owner.py')
                with patch.dict(sys.modules, requests=http, boto3=aws, runtime_config=config_module, bucket_owner=owner_module):
                    module = load_module('legacy_documents_' + job, directory / (job + '.py'))
                    module.datetime, module.time = clock, timer
                    module.main()
            elif side == 'lakehouse':
                config = native.load_config()
                if job == 'search_reindex_weekly':
                    native.reindex(config, http, native.required_secret('ETL_MEILISEARCH_API_KEY'), timer)
                else:
                    native.cleanup(config, aws, clock=clock)
            else:
                raise ValueError('Unknown engine: ' + side)
            outcome = {'status': 'success'}
        except SystemExit as error:
            outcome = {'status': 'exit', 'code': error.code}
        except Exception as error:
            outcome = {'status': 'error', 'type': type(error).__name__, 'message': str(error)}
    if job == 'search_reindex_weekly':
        state = dict(outcome=outcome, indexes=http.indexes, actions=http.actions, elapsed=timer.elapsed)
    else:
        state = dict(outcome=outcome, reports=aws.reports, actions=aws.actions,
                     objects=aws.objects, quarantine=aws.quarantine)
    return state, output.getvalue()


def records(job, scenario, state):
    common = {'outcome': state['outcome']}
    if job == 'search_reindex_weekly':
        for name in ['documents', 'files']:
            yield 'search_' + name, dict(scenario=scenario, identity=name,
                                         payload={**common, 'index': state['indexes'].get(name)})
        yield 'search_actions', dict(scenario=scenario, identity='actions',
                                     payload={**common, 'actions': state['actions'], 'elapsed': state['elapsed']})
    else:
        yield 'cleanup_report', dict(scenario=scenario, identity='report.json',
                                     payload={**common, 'reports': state['reports']})
        yield 'cleanup_actions', dict(scenario=scenario, identity='actions',
                                      payload={**common, 'actions': state['actions'], 'objects': state['objects'],
                                               'quarantine': state['quarantine']})


def run(path, day):
    raw = path.read_bytes()
    document = json.loads(raw)
    business_date(day)
    if document['business_date'] != day:
        raise ValueError('External fixture date differs')
    root = data_root() / 'external_parity' / day
    root.mkdir(parents=True, exist_ok=True)
    config = configparser.ConfigParser()
    config.read_dict(document['config'])
    config_path = root / 'fixture.ini'
    with config_path.open('w') as handle:
        config.write(handle)
    for side in ['legacy', 'lakehouse']:
        directory = root / side
        directory.mkdir(exist_ok=True)
        grouped = {name: [] for name in OUTPUTS}
        for category, job in [('search', 'search_reindex_weekly'), ('cleanup', 'storage_cleanup_daily')]:
            for scenario in document[category]:
                state, log = execute(side, job, copy.deepcopy(scenario), document, config_path)
                for name, row in records(job, scenario['name'], state):
                    grouped[name].append(row)
                (directory / (category + '-' + scenario['name'] + '.log')).write_text(log)
        for name, rows in grouped.items():
            temporary = directory / (name + '.tmp')
            with temporary.open('w', newline='') as handle:
                writer = csv.writer(handle, delimiter='|', lineterminator='\n')
                writer.writerow(['scenario', 'identity', 'payload'])
                writer.writerows([row['scenario'], row['identity'], json.dumps(row['payload'], sort_keys=True)] for row in rows)
            os.replace(temporary, directory / (name + '.psv'))
        print(f'documents.external.{side}: executed {len(document["search"])} search and {len(document["cleanup"])} cleanup scenarios', flush=True)
    if path.read_bytes() != raw:
        raise ValueError('External fixture changed between engines')
    sources = ['etl/scripts/search_reindex_weekly.py', 'etl/scripts/storage_cleanup_daily.py',
               'etl/scripts/runtime_config.py', 'etl/scripts/bucket_owner.py',
               'lakehouse/runtime/documents_external.py', 'lakehouse/parity/documents_external.py',
               'lakehouse/parity/documents_external_fakes.py']
    provenance = dict(business_date=day, fixture=str(path.resolve()), fixture_sha256=hashlib.sha256(raw).hexdigest(),
                      sources={name: hashlib.sha256((ROOT.parent / name).read_bytes()).hexdigest() for name in sources},
                      python=sys.version, clock=document['instant'], network='none: strict in-process injected fakes')
    (root / 'provenance.json').write_text(json.dumps(provenance, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--fixture', type=Path, required=True)
    parser.add_argument('--business-date', required=True)
    parser.add_argument('--generate', action='store_true')
    args = parser.parse_args()
    if args.generate:
        args.fixture.parent.mkdir(parents=True, exist_ok=True)
        args.fixture.write_text(json.dumps(fixture(args.business_date), indent=2) + '\n')
    run(args.fixture, args.business_date)


if __name__ == '__main__':
    main()
