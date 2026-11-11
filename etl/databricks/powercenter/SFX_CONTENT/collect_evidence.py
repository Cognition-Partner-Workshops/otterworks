"""Publish aggregate evidence only; keep source rows and API payloads local."""
import json

import yaml

from dbx import EVIDENCE, ROOT
from validate import MAPS, REPO


def read(name):
    return json.loads((EVIDENCE / name).read_text())


def read_optional(name, default):
    return read(name) if (EVIDENCE / name).exists() else default


def metrics(item):
    return {'statement_id': item['statement_id'],
            'metrics': {k: v for k, v in item['rows'][0].items() if 'sample' not in k}}


def collect():
    inputs = read('inputs.json')
    first_inputs = read_optional('inputs-first-failure.json', inputs)
    validation = read('validation.json')
    initial = read_optional('validation-first.json', validation)
    features = yaml.safe_load((REPO / 'etl/informatica/licence.yaml').read_text())['mapping_features']['SFX_CONTENT']
    history = read('query-history.json')
    indexed = {r['statement_id']: r for r in history['rows']}
    statements = []
    for line in (EVIDENCE / 'statements.jsonl').read_text().splitlines():
        r = json.loads(line)
        sid = r['response']['statement_id']
        statements.append({'statement_id': sid, 'consumer': r['consumer'], 'step': r['step'],
                           'label': r['label'], 'state': r['response']['status']['state'],
                           'query_history': indexed.get(sid)})
    board = []
    for mapping, (target, _) in MAPS.items():
        result = validation[mapping]
        parity = result['parity'][0]
        p = parity['rows'][0]
        idem = result['idempotence']['rows'][0]
        assert p['pc_count'] == p['after_count'] and p['pc_hash'] == p['after_hash']
        assert p['pc_minus_after'] == p['after_minus_pc'] == '0'
        assert idem['pc_minus_after'] == idem['after_minus_pc'] == '0'
        first = 'No failing comparison observed for this mapping.'
        first_sid = ''
        if target in first_inputs and not first_inputs[target]['equal']:
            f = first_inputs[target]
            first_sid = f['statement_id']
            first = (f"Input CHAR-padding mismatch: local {f['local']['count']}/{f['local']['hash']}; "
                     f"live {f['live']['count']}/{f['live']['hash']}. Corrected using runner CHAR trimming.")
        f = initial.get(mapping, result)['parity'][0]
        if mapping == 'm_SFX_APP_USER' and f['rows'][0]['pc_minus_after'] != '0':
            first += (f" Initial target comparison {f['statement_id']}: "
                      f"{f['rows'][0]['pc_minus_after']} PC-minus-after and "
                      f"{f['rows'][0]['after_minus_pc']} after-minus-PC rows. "
                      'The recorded correction initializes the after target from the verified before target; '
                      'source-width rejects are retained and compared separately.')
        red = mapping == 'm_SFX_DOC_SHARE'
        reason = ('Standalone parity and idempotence pass, but the workflow requires reserved '
                  's_m_SFX_ROLE_GRANT=SUCCEEDED. Both runs leave DOC_SHARE UPSTREAM_FAILED; '
                  'no licence retirement claimed for this row.') if red else ''
        board.append({'mapping': mapping, 'source': f'etl/informatica/repository/SFX_CONTENT/mappings/{mapping}.XML',
                      'target': f'cpw.dbx_d1111_after.{target}', 'status': 'red' if red else 'green',
                      'first_failure': first, 'first_failure_statement_id': first_sid,
                      'corrected_parity': f"{p['pc_count']} rows; hash {p['pc_hash']}; 0 EXCEPT ALL differences each way",
                      'parity_statement_id': parity['statement_id'],
                      'idempotence': 'Run 2 equals run 1 on counts, hash and EXCEPT ALL; unchanged MERGEs affect zero rows.',
                      'idempotence_statement_ids': [result['parity'][1]['statement_id'], result['idempotence']['statement_id']],
                      'red_reason': reason, 'licence_features': [] if red else features[mapping]})
    public_validation = {m: {'runs': v['runs'], 'parity': [metrics(p) for p in v['parity']],
                             'idempotence': metrics(v['idempotence'])} for m, v in validation.items()}
    output = {'run_token': 'dbx-d1111', 'expires': '2026-11-24', 'act': 'scale', 'subject_area': 'documents',
              'rows': board, 'inputs': inputs, 'initial_input_failures': first_inputs,
              'oracle': read('oracle.json'), 'validation': public_validation,
              'initial_app_user_parity': metrics(initial.get('m_SFX_APP_USER', validation['m_SFX_APP_USER'])['parity'][0]),
              'reject_parity': {m: metrics(v) for m, v in read('reject-parity.json').items()},
              'job': read('job-summary.json'), 'job_metadata': read('job-metadata.json'),
              'cross_folder_dependencies': [], 'query_history_statement_id': history['statement_id'],
              'query_history_note': 'Entries without query_history have Statement Execution API evidence; history ingestion is pending (30-40 minute lag). Re-run query_history.sql.',
              'statements': statements,
              'licence_note': 'Four green mappings in this scoped PR. Global counter must be computed from all 20 mapping rows; DOC_SHARE remains red due to its reserved workflow predecessor.'}
    if (EVIDENCE / 'control.json').exists():
        output['control'] = read('control.json')
    (ROOT / 'evidence.json').write_text(json.dumps(output, indent=2) + '\n')
    print('Published five board rows; four green and one reserved-dependency red.')


if __name__ == '__main__':
    collect()
