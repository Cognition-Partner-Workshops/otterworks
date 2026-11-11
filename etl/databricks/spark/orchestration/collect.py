"""run_token=dbx-d1111 expires=2026-11-24; collect the single daily run."""
import json
import time
from deploy import ROOT, api, save, status, sql

run_id = json.loads((ROOT / 'daily-run.json').read_text())['run_id']
while True:
    run = status(run_id)
    if run['state']['life_cycle_state'] in ('TERMINATED', 'SKIPPED', 'INTERNAL_ERROR'):
        break
    print(run['state'], flush=True)
    time.sleep(30)
tasks = []
for task in run.get('tasks', []):
    output = api('GET', f"2.1/jobs/runs/get-output?run_id={task['run_id']}")
    child_id = output.get('run_job_output', {}).get('run_id')
    if not child_id:
        child_id = status(task['run_id']).get('run_job_output', {}).get('run_id')
    tasks.append(dict(task_key=task['task_key'], task_run_id=task['run_id'],
                      child_run_id=child_id, state=task['state'],
                      error=output.get('error')))
result = dict(parent_run_id=run_id, state=run['state'], tasks=tasks)
save('run-evidence.json', result)
print(json.dumps(result, indent=2))
schema = sql('/* run=dbx-d1111 act=spark step=control-describe consumer=orchestration */\nDESCRIBE TABLE cpw.dbx_d1111_control.migration_control')
save('control-schema.json', schema)
print('CONTROL SCHEMA', schema.get('result'))
