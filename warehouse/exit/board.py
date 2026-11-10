"""Consumer migration parity board, with workflow-specific PR evidence."""
import html
import json
from pathlib import Path
import subprocess

from reads import OUT_OF_SCOPE, arguments, collect, registry

REPO = 'Cognition-Partner-Workshops/otterworks'


def api(path):
    return json.loads(subprocess.check_output(['gh', 'api', path], text=True))


def pull_requests(consumers):
    records = []
    for consumer in consumers:
        name = consumer['name']
        prs = api(f'repos/{REPO}/pulls?state=all&base=demo-snowflake-dw-exit&head=Cognition-Partner-Workshops:devin/sfx-d1110-consumer-{name}&per_page=100')
        for pr in prs:
            if pr['state'] == 'closed' and not pr.get('merged_at'):
                continue
            runs, page = [], 1
            while True:
                batch = api(f"repos/{REPO}/actions/runs?head_sha={pr['head']['sha']}&per_page=100&page={page}")['workflow_runs']
                runs.extend(batch)
                if len(batch) < 100:
                    break
                page += 1
            records.append({**pr, 'workflow_runs': runs})
    return records


def rows(data, consumers, prs):
    result = []
    for consumer in consumers:
        name = consumer['name']
        matches = [p for p in prs if p['base']['ref'] == 'demo-snowflake-dw-exit' and
                   p['head']['ref'] == f'devin/sfx-d1110-consumer-{name}' and
                   (p['state'] == 'open' or p.get('merged_at'))]
        pr = max(matches, key=lambda p: p['number']) if matches else None
        ci = 'missing'
        if pr:
            runs = [r for r in pr.get('workflow_runs', []) if r['head_sha'] == pr['head']['sha'] and
                    r['path'].split('@')[0] == consumer['workflow'] and r.get('event') == 'pull_request']
            if runs:
                run = max(runs, key=lambda r: (r.get('run_number', 0), r.get('run_attempt', 1), r.get('id', 0)))
                ci = run.get('conclusion') if run['status'] == 'completed' else run['status']
        status = 'Snowflake' if pr and pr.get('merged_at') else 'Teradata → Snowflake' if pr and ci == 'success' else 'Teradata'
        result.append([name, consumer['team'], consumer['teradata_service_account'],
                       data[name]['baseline'], data[name]['teradata'], data[name]['snowflake'],
                       pr['html_url'] if pr else '—', ci, status])
    for name, status in [('unmanaged', 'unmanaged — needs owner'), *((name, 'out of scope') for name in OUT_OF_SCOPE)]:
        row = data[name]
        result.append([name, '—', ', '.join(row['accounts']) or 'see DBQL', row['baseline'], row['teradata'], row['snowflake'], '—', '—', status])
    return result


HEADERS = ['Consumer', 'Team', 'Service account', 'Baseline TD (30d)', 'Window TD', 'Window SF', 'PR', 'PR workflow CI', 'consumers']


def markdown(records):
    def cell(value):
        return str(value).replace('|', '\\|').replace('\n', ' ')
    return '\n'.join(['| ' + ' | '.join(HEADERS) + ' |', '| ' + ' | '.join(['---'] * len(HEADERS)) + ' |'] +
                     ['| ' + ' | '.join(map(cell, row)) + ' |' for row in records])


def document(records):
    def cells(row, tag):
        return '<tr>' + ''.join(f'<{tag}>{html.escape(str(value))}</{tag}>' for value in row) + '</tr>'
    return ('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
            '<title>Finance warehouse consumer exit</title><style>body{font:16px system-ui;margin:2rem;color:#172b3a}'
            'table{border-collapse:collapse;width:100%}td,th{padding:.7rem;border:1px solid #ccd;text-align:left}'
            'th{background:#edf3f8}tr:nth-child(even){background:#f8fafc}</style><h1>Finance warehouse consumer exit</h1>'
            '<p>Run sfx-d1110 · UTC half-open reporting window · baseline 2026-10-11 to 2026-11-10</p><table><thead>' +
            cells(HEADERS, 'th') + '</thead><tbody>' + ''.join(cells(row, 'td') for row in records) + '</tbody></table></html>')


if __name__ == '__main__':
    parser = arguments(__doc__)
    parser.add_argument('--prs-json', type=Path, help='Offline list of GitHub PR objects with workflow_runs')
    parser.add_argument('--html', type=Path, required=True)
    args = parser.parse_args()
    data = collect(args, 'board')
    consumers = registry()
    prs = json.loads(args.prs_json.read_text()) if args.prs_json else pull_requests(consumers)
    records = rows(data, consumers, prs)
    args.html.write_text(document(records))
    print(markdown(records))
