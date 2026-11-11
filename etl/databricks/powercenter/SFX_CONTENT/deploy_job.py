"""Create the single SQL-warehouse job and run it twice, retaining reserved gaps."""
import base64
import json
import os
import time

from dbx import EVIDENCE, ROOT, api

WORKSPACE = '/Shared/dbx-d1111-expires-2026-11-24/SFX_CONTENT'


def deploy():
    api('POST','/api/2.0/workspace/mkdirs',{'path':WORKSPACE})
    generated = ROOT / 'job-sql'
    generated.mkdir(exist_ok=True)
    for path in list(ROOT.glob('m_SFX_*.sql')) + [ROOT / 'reserved_role_grant_dependency.sql']:
        if path.name.endswith('_parity.sql'):
            continue
        content=path.read_text()
        # The standalone validation reads frozen inputs. The workflow consumes
        # its own upstream outputs, exactly as the relational runner does.
        if path.stem=='m_SFX_APP_USER':
            content=content.replace('cpw.dbx_d1111_before.users__stg_app_user','cpw.dbx_d1111_after.users__stg_app_user')
        if path.stem=='m_SFX_DOCUMENT':
            content=content.replace('cpw.dbx_d1111_before.documents__stg_document','cpw.dbx_d1111_after.documents__stg_document')
            content=content.replace('cpw.dbx_d1111_before.users__app_user','cpw.dbx_d1111_after.users__app_user')
        content += '\n-- run_token=dbx-d1111 expires=2026-11-24 act=scale\n'
        (generated / path.name).write_text(content)
        api('POST','/api/2.0/workspace/import',{'path':WORKSPACE+'/'+path.name,
            'format':'RAW','overwrite':True,'content':base64.b64encode(content.encode()).decode()})
    body=json.loads((ROOT/'job.json').read_text().replace('${DATABRICKS_WAREHOUSE_ID}',os.environ['DATABRICKS_WAREHOUSE_ID']))
    saved=EVIDENCE/'job-created.json'
    if saved.exists():
        job=json.loads(saved.read_text())
        api('POST','/api/2.2/jobs/reset',{'job_id':job['job_id'],'new_settings':body})
    else:
        job=api('POST','/api/2.2/jobs/create',body)
        saved.write_text(json.dumps(job,indent=2))
    print('job_id',job['job_id'],flush=True)
    runs=[]
    for n in (1,2):
        r=api('POST','/api/2.2/jobs/run-now',{'job_id':job['job_id'],
            'idempotency_token':f"dbx-d1111-content-{job['job_id']}-{n}",
            'job_parameters':{'run_token':'dbx-d1111','expires':'2026-11-24','act':'scale'}})
        rid=r['run_id']
        print('run_id',rid,flush=True)
        deadline=time.monotonic()+600
        while True:
            detail=api('GET',f'/api/2.2/jobs/runs/get?run_id={rid}')
            if detail['state']['life_cycle_state'] in ('TERMINATED','SKIPPED','INTERNAL_ERROR'):
                break
            if time.monotonic()>deadline:
                raise TimeoutError(f'Job run {rid} did not finish within ten minutes')
            time.sleep(5)
        (EVIDENCE/f'job-run-{n}.json').write_text(json.dumps(detail,indent=2))
        summary={'run_id':str(rid),'state':detail['state'],
                 'tasks':[{'task_key':t['task_key'],'run_id':str(t['run_id']),'state':t['state']} for t in detail['tasks']]}
        runs.append(summary)
        (EVIDENCE/'job-summary.json').write_text(json.dumps({'job_id':str(job['job_id']),'runs':runs,'tags':body['tags']},indent=2))
        print(json.dumps(summary),flush=True)


if __name__=='__main__':
    deploy()
