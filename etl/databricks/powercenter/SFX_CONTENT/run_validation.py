"""Load oracle results, execute conversions twice, and capture parity evidence."""
import json

from dbx import EVIDENCE, ROOT, rows, sql
from validate import MAPS, REPO, aggregate, projection

COMMENT = "run_token=dbx-d1111 expires=2026-11-24"
PROPS = "TBLPROPERTIES ('run_token'='dbx-d1111','expires'='2026-11-24')"


def literal(v):
    return "NULL" if v is None else "'" + str(v).replace("'", "''") + "'"


def statements(path):
    return [s.strip() for s in path.read_text().split(';') if s.strip()]


def failed_runs(result):
    runs = result.get('runs', [])
    return (len(runs) != 2 or any(not run or any(
        call.get('status', {}).get('state') != 'SUCCEEDED' for call in run) for run in runs))


def setup(execute=True):
    ddl = []
    for mapping, (target, cols) in MAPS.items():
        projected = [f"{x} AS {c}" for x, c in zip(projection(target, cols), cols)]
        ddl.append(f"/* run=dbx-d1111 act=scale step=ddl consumer={mapping} */\n"
            f"CREATE TABLE IF NOT EXISTS cpw.dbx_d1111_after.{target}\nUSING DELTA COMMENT '{COMMENT}' {PROPS}\n"
            f"AS SELECT {','.join(projected)} FROM cpw.dbx_d1111_before.{target};")
        ddl.append(f"/* run=dbx-d1111 act=scale step=baseline-target-state consumer={mapping} */\n"
            f"INSERT OVERWRITE cpw.dbx_d1111_after.{target} "
            f"SELECT {','.join(projected)} FROM cpw.dbx_d1111_before.{target};")
        if mapping in ("m_SFX_APP_USER", "m_SFX_DOCUMENT"):
            reject_cols = [c for c in cols if c != 'file_type']
            ddl.append(f"/* run=dbx-d1111 act=scale step=ddl consumer={mapping} */\n"
                f"CREATE TABLE IF NOT EXISTS cpw.dbx_d1111_after.{target}__reject\nUSING DELTA COMMENT '{COMMENT}' {PROPS}\n"
                f"AS SELECT {','.join(reject_cols)},cast(NULL AS INT) AS row_type,cast(NULL AS STRING) AS reason "
                f"FROM cpw.dbx_d1111_before.{target} WHERE false;")
    (ROOT / 'setup.sql').write_text('\n\n'.join(ddl)+'\n')
    if execute:
        for stmt in statements(ROOT / 'setup.sql'):
            sql(stmt, 'SFX_CONTENT', 'ddl', 'setup')


def load_oracle():
    ids = {}
    for mapping, (target, cols) in MAPS.items():
        table = f'cpw.dbx_d1111_parity.{target}__pc_before'
        sql(f"CREATE TABLE IF NOT EXISTS {table} USING DELTA COMMENT '{COMMENT}' {PROPS} "
            f"AS SELECT {','.join(cols)} FROM cpw.dbx_d1111_after.{target} WHERE false", mapping, 'ddl', 'pc-before')
        sql(f"DELETE FROM {table}", mapping, 'oracle-load', 'clear-pc-before')
        data = json.loads((EVIDENCE / (mapping+'_rows.json')).read_text())
        ids[mapping] = []
        for i in range(0, len(data), 100):
            values = ',\n'.join('('+','.join(literal(v) for v in r)+')' for r in data[i:i+100])
            r = sql(f"INSERT INTO {table} VALUES {values}", mapping, 'oracle-load', 'pc-before')
            ids[mapping].append(r['statement_id'])
    return ids


def comparison(target, cols, before=None):
    before = before or f'cpw.dbx_d1111_parity.{target}__pc_before'
    after = f'cpw.dbx_d1111_after.{target}'
    canon = ",".join(f"coalesce(cast({c} AS STRING),'<NULL>')" for c in cols)
    return f"""WITH p AS (SELECT {','.join(cols)} FROM {before}),
    a AS (SELECT {','.join(cols)} FROM {after}),
    p_minus_a AS (SELECT * FROM p EXCEPT ALL SELECT * FROM a),
    a_minus_p AS (SELECT * FROM a EXCEPT ALL SELECT * FROM p),
    ps AS ({aggregate('p',cols)}), ats AS ({aggregate('a',cols)})
    SELECT ps.count AS pc_count,ats.count AS after_count,ps.hash AS pc_hash,ats.hash AS after_hash,
      (SELECT count(*) FROM p_minus_a) AS pc_minus_after,
      (SELECT count(*) FROM a_minus_p) AS after_minus_pc,
      (SELECT to_json(collect_list(named_struct('row',canonical))) FROM
        (SELECT concat_ws('|',{canon}) AS canonical FROM p_minus_a LIMIT 20)) AS pc_sample,
      (SELECT to_json(collect_list(named_struct('row',canonical))) FROM
        (SELECT concat_ws('|',{canon}) AS canonical FROM a_minus_p LIMIT 20)) AS after_sample
    FROM ps CROSS JOIN ats"""


def execute(only=None):
    saved=EVIDENCE / 'validation.json'
    results = json.loads(saved.read_text()) if saved.exists() else {}
    for mapping, (target, cols) in MAPS.items():
        if only and mapping not in only:
            continue
        result = {'runs': [], 'parity': []}
        for run in (1,2):
            calls = []
            for stmt in statements(ROOT / (mapping+'.sql')):
                r = sql(stmt,mapping,f'convert-run{run}', 'conversion',fail=False)
                calls.append({'statement_id':r['statement_id'],'status':r['status'],'metrics':rows(r)})
                if r['status']['state']!='SUCCEEDED':
                    break
            result['runs'].append(calls)
            q = comparison(target, cols)
            (ROOT / (mapping+'_parity.sql')).write_text(
                f'/* run=dbx-d1111 act=scale step=parity consumer={mapping} */\n'+q+';\n')
            r=sql(q,mapping,'parity' if run==1 else 'idempotence','comparison')
            result['parity'].append({'statement_id':r['statement_id'],'rows':rows(r)})
            if run==1:
                snap=f'cpw.dbx_d1111_parity.{target}__run1'
                sql(f"CREATE TABLE IF NOT EXISTS {snap} USING DELTA COMMENT '{COMMENT}' {PROPS} AS SELECT * FROM cpw.dbx_d1111_after.{target} WHERE false",mapping,'ddl','run1-snapshot')
                sql(f"INSERT OVERWRITE {snap} SELECT * FROM cpw.dbx_d1111_after.{target}",mapping,'idempotence','save-run1')
        r=sql(comparison(target,cols,f'cpw.dbx_d1111_parity.{target}__run1'),mapping,'idempotence','run1-vs-run2')
        result['idempotence']={'statement_id':r['statement_id'],'rows':rows(r)}
        if mapping in ('m_SFX_APP_USER','m_SFX_DOCUMENT'):
            r=sql(aggregate(f'cpw.dbx_d1111_after.{target}__reject',[c for c in cols if c!='file_type']),mapping,'parity','reject-count-hash')
            result['rejects']={'statement_id':r['statement_id'],'rows':rows(r)}
        results[mapping]=result
        (EVIDENCE / 'validation.json').write_text(json.dumps(results,indent=2))
        first_path = EVIDENCE / 'validation-first.json'
        first = json.loads(first_path.read_text()) if first_path.exists() else {}
        failed = failed_runs(result) or any(p['rows'][0]['pc_minus_after'] != '0' or p['rows'][0]['after_minus_pc'] != '0'
                     for p in result['parity'])
        if failed and mapping not in first:
            first[mapping] = result
            first_path.write_text(json.dumps(first, indent=2))
        print(mapping,json.dumps({'parity': [{k:v for k,v in p['rows'][0].items() if 'sample' not in k} for p in result['parity']],
             'idempotence':result['idempotence']['statement_id']}),flush=True)


def compare_rejects():
    results = {}
    for mapping in ('m_SFX_APP_USER', 'm_SFX_DOCUMENT'):
        target, physical_cols = MAPS[mapping]
        cols = [c for c in physical_cols if c != 'file_type']
        name = target.split('__')[1]
        bad = REPO / f'etl/informatica/infa_shared/dbx-d1111-documents/BadFiles/{name}1.bad'
        if bad.exists():
            data = [line.split(',D,')[1:] for line in bad.read_text().splitlines()]
        else:
            # The runner removes an empty reject file (engine.py write_target).
            outcome = json.loads((EVIDENCE / 'oracle.json').read_text())[mapping]
            assert outcome['returncode'] == 0 and outcome['last_line'][0].endswith('rejected=0')
            data = []
        assert all(len(r) == len(cols) for r in data), 'Unexpected runner reject-file format'
        table = f'cpw.dbx_d1111_parity.{target}__reject__pc_before'
        sql(f"CREATE TABLE IF NOT EXISTS {table} USING DELTA COMMENT '{COMMENT}' {PROPS} "
            f"AS SELECT {','.join(cols)} FROM cpw.dbx_d1111_after.{target} WHERE false", mapping, 'ddl', 'reject-oracle')
        sql(f'DELETE FROM {table}', mapping, 'oracle-load', 'clear-reject-oracle')
        for i in range(0, len(data), 100):
            values = ','.join('(' + ','.join(literal(v if v != '' else None) for v in r) + ')' for r in data[i:i+100])
            sql(f'INSERT INTO {table} VALUES {values}', mapping, 'oracle-load', 'reject-oracle')
        result = sql(comparison(target + '__reject', cols, table), mapping, 'parity', 'reject-comparison')
        results[mapping] = {'statement_id': result['statement_id'], 'rows': rows(result)}
        p = rows(result)[0]
        assert p['pc_minus_after'] == p['after_minus_pc'] == '0', 'Rejected-row parity failed'
        print(mapping, 'rejects', p['after_count'], result['statement_id'], flush=True)
    (EVIDENCE / 'reject-parity.json').write_text(json.dumps(results, indent=2))


if __name__=='__main__':
    setup()
    load_oracle()
    execute()
    compare_rejects()
