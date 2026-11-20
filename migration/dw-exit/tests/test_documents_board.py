import json
import sys
from types import SimpleNamespace
from pathlib import Path

import pytest
import yaml

from parity import object_board as board
from warehouse.run_config import RunConfig

ROOT = Path(__file__).resolve().parents[3]


def objects():
    manifest = yaml.safe_load((ROOT/'migration/dw-exit/manifest.yaml').read_text())
    return [obj for obj in board.relation_contract(manifest['objects']) if obj['subject_area']=='documents']


@pytest.mark.parametrize('failure', [False, True])
def test_shared_materializer_uses_frozen_proof_and_fails_closed(monkeypatch, tmp_path, failure):
    def prove(pre_pc, landing, namespace, day, objects):
        assert pre_pc == tmp_path and namespace == 'scoped' and day == '20261109'
        assert objects == []
        if failure:
            raise ValueError('missing frozen capture')
        return {'objects': []}
    monkeypatch.setitem(sys.modules, 'documents.prove_local', SimpleNamespace(prove=prove))
    monkeypatch.setattr(board.spark_documents, 'materialize', lambda *args: (set(), {}, {}))
    monkeypatch.setattr(board, 'documents_validated_history', lambda: {'passed': True})
    evidence = board.materialize_documents([], 'scoped', '20261109', tmp_path)
    assert evidence['objects'] == []
    assert ('missing frozen capture' in evidence.get('error', '')) == failure
    assert evidence['spark']['jobs'] == {}


def test_documents_board_is_reproducible_from_recorded_evidence():
    evidence = json.loads((board.DOCUMENTS_DIRECTORY/'evidence.json').read_text())
    manifest = yaml.safe_load((ROOT/'migration/dw-exit/manifest.yaml').read_text())
    manifest['objects'] = objects()
    rows = board.build_board(manifest, documents_evidence=evidence)['rows']
    assert len(rows)==len({row['id'] for row in rows})==59
    assert all(row['snowflake']=='red' for row in rows)
    binary = next(row for row in rows if row['name']=='file_object_binary_extract')
    assert binary['row_count']=={'before':400,'after':400}
    alert = next(row for row in rows if row['name']=='security_alert_anomaly')
    assert alert['keyed_row_hash']['SFX_AUDIT.SPARK_ALERT_ANOMALY']['difference']==0
    for row in rows:
        p = row['provenance']
        for link in p['source']+list(p['metrics'].values())+p['converted']+[row['metric_evidence']]:
            file = ROOT/link['file']
            assert file.is_file()
            if link['start_line'] is not None and board.DOCUMENTS_BRANCH in link['url']:
                assert 1<=link['start_line']<=link['end_line']<=len(file.read_text().splitlines())
        if row['status']=='retired':
            assert row['retirement']['deletion_approved']
            assert row['retirement']['drop_order'] == ['SFX_DOCUMENTS.V_SEARCH_HISTORY', 'SFX_DOCUMENTS.SEARCH_INDEX_LOG']
        else:
            assert p['converted']
            if row['row_count'] is None:
                assert row['name'] in ('SFX_DOCUMENTS.STG_SEARCH_INDEX_LOG', 'documents_search_index_log')
                assert row['status'] == 'red' and row['reason']
                assert row['column_profile'] is row['keyed_row_hash'] is None
            else:
                assert row['column_profile'] and row['keyed_row_hash']
    staging = next(row for row in rows if row['name']=='SFX_DOCUMENTS.STG_SEARCH_INDEX_LOG')
    assert staging['target_type'] == 'dbt_model' and staging['status'] == 'red'
    assert 'retirement' not in staging
    assert next(r for r in rows if r['name']=='documents_search_index_log')['status'] == 'red'
    assert {r['name'] for r in rows if r['status']=='retired'} == {'SFX_DOCUMENTS.V_SEARCH_HISTORY', 'SFX_DOCUMENTS.SEARCH_INDEX_LOG'}
    assert '| Object |' in board.documents_markdown(rows, {})
    for row in (row for row in rows if row['status']=='approved_deviation'):
        assert row['measurement_status']=='red'
        for proof in row['owner_decision_evidence']:
            assert len(proof['scope_document_ids'])==50
            assert proof['outside_scope_rows']==0
            assert set(proof['mismatching_key_values']) <= set(proof['scope_key_values'])
            assert proof['approved_comparison']['passed']


def test_replay_rejects_missing_or_stale_artifacts(tmp_path,monkeypatch):
    missing = tmp_path/'missing.json'
    with pytest.raises(OSError):
        board.documents_validated_history(missing)
    monkeypatch.setattr(board,'ROOT',tmp_path)
    monkeypatch.setattr(board.spark_documents,'ROOT',tmp_path)
    namespace = RunConfig.from_env().before_namespace
    replay = {'passed':True,'dates':['2026-11-19','2026-11-20'],
              'steps':[{'measurement':{'passed':True}}], 'namespace':namespace}
    for field in ('landing_sha256','output_sha256','execution_log_sha256','conversion_sha256','legacy_code_sha256'):
        output = tmp_path/'etl/spark/.data'/namespace/'lake/documents/file_object_binary_extract/run_date=2026-11-20/part.parquet'
        file = output if field=='output_sha256' else tmp_path/field
        file.parent.mkdir(parents=True,exist_ok=True)
        file.write_text('fixture')
        replay[field] = board.spark_documents.checksums([file])
    normal = tmp_path/'normal.json'
    normal.write_text(json.dumps(replay))
    assert board.documents_validated_history(normal)['passed']
    replay['conversion_sha256'][next(iter(replay['conversion_sha256']))] = 'not current'
    stale = tmp_path/'stale.json'
    stale.write_text(json.dumps(replay))
    with pytest.raises(ValueError,match='Stale'):
        board.documents_validated_history(stale)
    replay['passed'] = False
    stale.write_text(json.dumps(replay))
    with pytest.raises(ValueError,match='not passed'):
        board.documents_validated_history(stale)
