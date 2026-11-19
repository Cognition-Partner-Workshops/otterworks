import json
from pathlib import Path

import pytest
import yaml

from parity import documents_board, object_board, provenance

ROOT = Path(__file__).resolve().parents[3]


def objects():
    return [o for o in yaml.safe_load((ROOT/'migration/dw-exit/manifest.yaml').read_text())['objects'] if o['subject_area']=='documents']


def test_documents_board_has_real_metrics_and_independent_denied_leg():
    evidence = json.loads((ROOT/'migration/dw-exit/documents/evidence.json').read_text())
    manifest = {'objects':objects()}
    measured = documents_board.object_measurements(manifest,evidence)
    preflight = json.loads((ROOT/'migration/dw-exit/parity/snowflake-preflight.json').read_text())
    board = object_board.build_board(manifest,subject_evidence={'documents':measured},preflight=preflight)
    summary = board['summary']['documents']
    assert (summary['total'],summary['local_green'],summary['local_amber'],summary['local_red'],summary['retired'])==(59,45,1,9,4)
    assert all(r['snowflake']=='red' and r['snowflake_reason']==preflight['reason'] for r in board['rows'])
    binary = next(r for r in board['rows'] if r['name']=='file_object_binary_extract')
    assert binary['row_count']=={'before':400,'after':400}
    alert = next(r for r in board['rows'] if r['name']=='security_alert_anomaly')
    assert alert['keyed_row_hash']['SFX_AUDIT.SPARK_ALERT_ANOMALY']['difference']==0
    assert alert['row_count']=={'before':400,'after':400}
    for row in board['rows']:
        p = row['provenance']
        for entry in p['source']+list(p['metrics'].values())+[v for entries in p['converted'].values() for v in entries]+list(row.get('metric_evidence',{}).values()):
            assert '/blob/devin/sfx1119-documents-migration/' in entry['url']
            assert 1<=entry['start_line']<=entry['end_line']<=len((ROOT/entry['file']).read_text().splitlines())
        if row['status']!='retired':
            assert p['converted'] and row['row_count'] is not None
    text = provenance.markdown(board['rows'],evidence)
    assert '45 green / 1 amber / 9 red / 4 retire candidates' in text
    assert 'spark_binary_two_date_history' in text


def test_missing_documents_proof_never_reuses_cached_green():
    board = object_board.build_board({'objects':objects()})
    assert all(r.get('measurement_status',r['status'])=='red' and r['row_count'] is None for r in board['rows'])
    assert sum(r['status']=='amber' for r in board['rows']) == 1
    denied = object_board.build_board({'objects':objects()},target='snowflake')
    assert all(r['status']=='red' and r['snowflake']=='red' for r in denied['rows'])


def test_replay_rejects_missing_or_stale_artifacts(tmp_path,monkeypatch):
    missing = tmp_path/'missing.json'
    with pytest.raises(OSError):
        documents_board.validated_history(missing)
    monkeypatch.setattr(documents_board,'ROOT',tmp_path)
    monkeypatch.setattr(documents_board.spark_documents,'ROOT',tmp_path)
    replay = {'passed':True,'dates':['2026-11-18','2026-11-19'],'steps':[{'measurement':{'passed':True}}],
              'namespace':'sfx-1119-before'}
    for field in ('landing_sha256','output_sha256','execution_log_sha256','conversion_sha256','legacy_code_sha256'):
        file = tmp_path/'etl/spark/.data/sfx-1119-before/lake/documents/file_object_binary_extract/run_date=2026-11-19/part.parquet' if field=='output_sha256' else tmp_path/field
        file.parent.mkdir(parents=True,exist_ok=True)
        file.write_text('fixture')
        replay[field] = documents_board.spark_documents.checksums([file])
    normal = tmp_path/'normal.json'
    normal.write_text(json.dumps(replay))
    assert documents_board.validated_history(normal)['passed']
    replay['conversion_sha256'][next(iter(replay['conversion_sha256']))] = 'not current'
    stale = tmp_path/'stale.json'
    stale.write_text(json.dumps(replay))
    with pytest.raises(ValueError,match='Stale'):
        documents_board.validated_history(stale)
    replay['passed'] = False
    stale.write_text(json.dumps(replay))
    with pytest.raises(ValueError,match='not passed'):
        documents_board.validated_history(stale)


def test_branch_selection_does_not_move_billing_provenance():
    billing = provenance.metric_links('billing')
    documents = provenance.metric_links('documents')
    assert set(billing)=={'counts','profiles','hashes'}
    assert set(documents)=={'counts','profiles','hashes','diffs'}
    assert all('/blob/devin/sfx1119-billing-parity/' in v['url'] for v in billing.values())
    assert all('/blob/devin/sfx1119-documents-migration/' in v['url'] for v in documents.values())
    assert billing['counts']['end_line']<documents['counts']['end_line']
