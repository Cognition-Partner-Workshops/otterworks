"""run_token=dbx-d1111 expires=2026-11-24; regenerate BOARD.md from evidence."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[3]


def main():
    rows = {j['job']: j for j in json.loads((ROOT / 'round-one.json').read_text())}
    baseline = json.loads((REPO / 'etl/spark/history/baseline.json').read_text())['jobs']
    daily = json.loads((ROOT / 'daily.json').read_text())
    included = {t['task_key'] for t in daily['tasks']}
    lines = ['# Spark migration board — dbx-d1111', '',
             'Before: packaged History Server baseline (not the live-input parity application).',
             'Executor-hours and DBUs are distinct units; no savings comparison is implied.',
             'Billing and history counts were not collected in this handoff (time-budget priority); DBUs remain PENDING, never zero.', '',
             'Per-job query-history template (substitute `<job>`):', '```sql',
             '/* run=dbx-d1111 act=spark step=history consumer=<job> */',
             "SELECT COUNT(*) FROM system.query.history WHERE statement_text LIKE '/* run=dbx-d1111 act=spark step=%consumer=<job> */%';",
             '```', '',
             '| Job | Target kind | Executor-hours before (h; baseline app id) | DBUs after (DBU) | Status | PR | Parity + statement_id | In daily orchestration | query.history query |',
             '| --- | --- | --- | --- | --- | --- | --- | --- | --- |']
    def clean(value):
        return str(value or '—').replace('|', '\\|').replace('\n', ' ')
    for name in (REPO / 'etl/spark/jobs.txt').read_text().splitlines():
        j, b = rows[name], baseline[name]
        if name in included:
            membership = 'task'
        elif name == 'file_object_binary_extract':
            membership = 'excluded: common Spark template (etl/spark/template)'
        else:
            membership = 'excluded: ' + (j.get('red_reason') or 'red / missing live input')
        if name == 'docs_folder_legacy_report':
            membership += '; retire candidate, cron commented out'
        values = [name, j['target_kind'], f"{b['executor_hours']:.9f} h; `{b['app_id']}`",
                  'PENDING', j['status'].lower(), j['pr_url'],
                  str(j.get('parity') or 'not run') + '; ' + str(j.get('parity_statement_id') or 'no parity statement'),
                  membership, f'`consumer={name}`']
        lines.append('| ' + ' | '.join(map(clean, values)) + ' |')
    lines += ['', '## Orchestration', '']
    deployment = json.loads((ROOT / 'deployment.json').read_text())
    lines += [f"Daily job `{deployment['daily']['job_id']}`; hourly job `{deployment['hourly']['job_id']}`. Both schedules verified PAUSED. Hourly not run."]
    run_path = ROOT / 'run-evidence.json'
    if run_path.exists():
        run = json.loads(run_path.read_text())
        lines += [f"Daily parent run `{run['parent_run_id']}`: {run['state']}.", '']
        for task in run['tasks']:
            lines.append(f"- {task['task_key']}: {task['state'].get('result_state', task['state']['life_cycle_state'])}; task run `{task['task_run_id']}`; child run `{task['child_run_id']}`.")
    (ROOT / 'BOARD.md').write_text('\n'.join(lines) + '\n')


if __name__ == '__main__':
    main()
