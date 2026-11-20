"""Source ranges and metric implementation links for the measured board."""
import ast
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[3]
BRANCH = 'devin/sfg1120-content'
BASE = 'https://github.com/Cognition-Partner-Workshops/otterworks/blob/' + BRANCH + '/'


def link(path, start=1, end=None, branch=BRANCH):
    path = Path(path)
    end = end or max(1, len((ROOT / path).read_text().splitlines()))
    return {'file': path.as_posix(), 'start_line': start, 'end_line': end,
            'url': f'https://github.com/Cognition-Partner-Workshops/otterworks/blob/{branch}/{path.as_posix()}#L{start}-L{end}'}


def metric_links():
    path = Path('migration/dw-exit/parity/object_board.py')
    nodes = {n.name:n for n in ast.parse((ROOT/path).read_text()).body if isinstance(n,ast.FunctionDef)}
    return {metric:link(path,nodes[function].lineno,nodes[function].end_lineno)
            for metric,function in [('counts','compare'),('profiles','measure'),('hashes','compare')]}


def content_provenance(obj):
    branch = 'devin/sfg1120-content'
    def entry(path, start=1, end=None):
        return link(path, start, end, branch=branch)
    xml = obj['source']
    precision = [entry(xml, number, number) for number, line in enumerate((ROOT/xml).read_text().splitlines(), 1)
                 if 'NAME="DISPLAY_NAME"' in line and 'PRECISION="60"' in line
                 and ('<SOURCEFIELD' in line or '<TRANSFORMFIELD' in line)]
    model = 'warehouse/dbt/models/pc/content/pc_content__stg_app_user.sql'
    model_line = next(n for n, line in enumerate((ROOT/model).read_text().splitlines(), 1) if 'as DISPLAY_NAME' in line)
    return {'source': [entry(xml)], 'converted': {'procedure': [entry('migration/dw-exit/content/workflow.sql')],
            'compiler': [entry('migration/dw-exit/content/convert.py')]},
            'decision': precision + [entry(model, model_line, model_line)],
            'metrics': {key: dict(value, url=value['url'].replace(BRANCH, branch)) for key, value in metric_links().items()}}


def content_markdown(rows):
    content = [row for row in rows if row['subject_area'] == 'content']
    if not content:
        return ''
    lines = ['\n## Content parity provenance', '',
             'BEFORE: actual PowerCenter workflow on the Teradata emulator; AFTER: shipped procedure body on DuckDB,',
             'using identical landing inputs and typed pre-workflow tables. TEAM_MEMBER remains untouched.',
             'Snowflake: **red** — '+content[0]['snowflake_reason']+'.', '',
             '| Object | Local DuckDB | Snowflake | Source | Converted procedure | Metrics |',
             '|---|---|---|---|---|---|']
    def anchors(entries):
        return '<br>'.join(f"[{e['file']}:{e['start_line']}–{e['end_line']}]({e['url']})" for e in entries)
    for row in content:
        p = row['provenance']
        lines.append(f"| {row['name']} | {row['local_duckdb']} | {row['snowflake']} | {anchors(p['source'])} | {anchors(p['converted']['procedure'])} | {anchors(p['metrics'].values())} |")
        lines += ['', row['reason'] or 'All declared outputs match.', '',
                  'Decision evidence: '+anchors(p['decision']), '',
                  '| Relation | BEFORE rows | AFTER rows | Profiles | Keyed hashes |', '|---|---:|---:|---|---|']
        for relation, result in row.get('relation_results', {}).items():
            counts = result['row_count']
            profiles = 'match' if result['column_profile']['before'] == result['column_profile']['after'] else 'differ'
            hashes = result['keyed_row_hash']['difference']
            lines.append(f"| {relation} | {counts['before']} | {counts['after']} | {profiles} | {'match' if not hashes else str(hashes)+' unmatched occurrences'} |")
        lines += ['', 'Samples for every differing key are recorded in `board.json` → `sampled_differences`.', '']
    return '\n'.join(lines).rstrip()+'\n'
