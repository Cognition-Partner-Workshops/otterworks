from copy import deepcopy
from pathlib import Path

import yaml

import assess
from parity import object_board

ROOT = Path(__file__).resolve().parents[3]


def test_proof_contract_does_not_change_approved_manifest():
    manifest = yaml.safe_load((ROOT/'migration/dw-exit/manifest.yaml').read_text())
    original = deepcopy(manifest)
    objects = object_board.relation_contract(manifest['objects'])
    assert manifest == original
    assert manifest['objects'] == assess.build()['objects']
    assert object_board.relation_contract([]) == []
    for obj in objects:
        if obj['subject_area'] == 'audit' and obj['system'] == 'powercenter' and obj['target_type'] != 'retire':
            assert all(name.startswith('SFX_AUDIT.') for name in obj['output_relations'])
        if obj['subject_area'] == 'users' and obj['system'] == 'spark':
            assert obj['output_relations'] == ['SFX_SPARK.'+obj['name'].upper()]


def test_audit_powercenter_never_reuses_batch_measurements():
    manifest = yaml.safe_load((ROOT/'migration/dw-exit/manifest.yaml').read_text())
    obj = next(o for o in manifest['objects'] if o['name'] == 'm_SFX_AUDIT_EVENT')
    unavailable = object_board.build_board({'objects':[obj]})['rows'][0]
    assert unavailable['status'] == 'red'
    assert unavailable['row_count'] is None
    result = dict(passed=True,row_count=dict(before=0,after=0),column_profile={},
                  keyed_row_hash=dict(difference=0),sampled_differences=[],comparison_rules={})
    proof = {'measurements':{'SFX_AUDIT.AUDIT_EVENT':result}}
    row = object_board.build_board({'objects':[obj]},audit_pc_results=proof)['rows'][0]
    assert row['local_duckdb'] == 'green'
    assert row['row_count'] == dict(before=0,after=0)
    result['passed'] = False
    row = object_board.build_board({'objects':[obj]},audit_pc_results=proof)['rows'][0]
    assert row['local_duckdb'] == 'red'
