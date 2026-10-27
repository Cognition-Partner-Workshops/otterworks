#!/usr/bin/env python3
"""Validate the published discovery dataset against the checked-out source."""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PREFIX = 'industries/manufacturing/global-fleet/'
REF = re.compile(r'(industries/manufacturing/global-fleet/[^\s:;,()\[\]"\'<>]+):(\d+)(?:-(\d+))?')
ID = re.compile(r'\b(?:MF|JP)-R\d+\b')
SHORT_REF = re.compile(r'(?<![\w/])(?:[\w.-]+/)*[\w.-]+\.(?:java|xhtml|sql|cbl|ads|ddl|md|sh|jcl|map|dlg|cpy|dat|txt):\d+')


def normalized(text):
    return ' '.join(text.split())


def validate(directory=HERE, root=ROOT):
    problems = []
    documents = {}
    cache = {}

    def error(where, message):
        problems.append(f'{where}: {message}')

    def lines(path):
        if path not in cache:
            file = root / path
            cache[path] = file.read_text().splitlines() if file.is_file() else None
        return cache[path]

    def check_ref(match, where):
        path, start, end = match.groups()
        source = lines(path)
        a, b = int(start), int(end or start)
        if source is None:
            error(where, f'source file does not exist: {path}')
        elif not 1 <= a <= b <= len(source):
            error(where, f'line range outside file: {match[0]} ({len(source)} lines)')

    def walk(value, where, key=''):
        if isinstance(value, dict):
            for k, v in value.items():
                walk(v, f'{where}.{k}', k)
        elif isinstance(value, list):
            for i, v in enumerate(value):
                walk(v, f'{where}[{i}]', key)
        elif isinstance(value, str):
            for match in SHORT_REF.finditer(value):
                if not match[0].startswith(PREFIX):
                    error(where, f'non-canonical source reference: {match[0]}')
            for match in REF.finditer(value):
                check_ref(match, where)
                if re.match(r',\d', value[match.end():]):
                    error(where, f'comma-list citation: {value}')
            if key in ('source', 'sources'):
                if not REF.fullmatch(value):
                    error(where, f'expected repository path:start[-end]: {value}')
            if key in ('sources_read', 'entry_points'):
                if not value.startswith(PREFIX) or not (root / value).exists():
                    error(where, f'whole-file path does not exist: {value}')

    for file in sorted(directory.rglob('*.json')):
        name = file.relative_to(directory).as_posix()
        try:
            documents[name] = json.loads(file.read_text())
        except (ValueError, OSError) as exc:
            error(name, f'invalid JSON: {exc}')
    if not documents:
        error(str(directory), 'no JSON data files')
    rule_ids = set()
    question_ids = set()
    all_ids = set()
    for name, doc in documents.items():
        walk(doc, name)
        if not name.startswith('rules/'):
            continue
        for kind, ids in [('rules', rule_ids), ('navigation_questions', question_ids)]:
            for item in doc.get(kind, []):
                ident = item.get('id')
                where = f'{name}:{ident}'
                if not ident or ident in all_ids:
                    error(where, f'missing or duplicate {kind} id')
                ids.add(ident)
                all_ids.add(ident)
                sources = item.get('sources', [])
                if not sources:
                    error(where, 'no source')
                if kind != 'rules':
                    continue
                evidence = item.get('evidence', '')
                parts = [normalized(p) for p in evidence.split('...') if normalized(p)]
                found = False
                for source in sources:
                    match = REF.fullmatch(source)
                    if match is None:
                        continue
                    path, start, end = match.groups()
                    content = lines(path)
                    if content is None:
                        continue
                    text = normalized('\n'.join(content[int(start)-1:int(end or start)]))
                    offset = 0
                    for part in parts:
                        at = text.find(part, offset)
                        if at < 0:
                            break
                        offset = at + len(part)
                    else:
                        if parts:
                            found = True
                if not found:
                    error(where, 'evidence not found in any single cited range')
    if 'crosscheck.json' in documents:
        for ident in sorted(set(ID.findall(json.dumps(documents['crosscheck.json']))) - rule_ids):
            error('crosscheck.json', f'undefined rule id {ident}')
    paired_ids = {
        ident
        for pair in documents.get('crosscheck.json', {}).get('rule_pairs', [])
        for side in ('mainframe_rule_ids', 'portal_rule_ids')
        for ident in pair.get(side, [])
    }
    for ident in sorted(rule_ids - paired_ids):
        error('crosscheck.json', f'rule id absent from final rule_pairs: {ident}')
    return problems, documents


def main():
    problems, documents = validate()
    if problems:
        for problem in problems:
            print(problem)
        print(f'FAIL: {len(problems)} problem(s)')
        return 1
    print(f'PASS: {len(documents)} JSON files; source references, unique IDs, evidence, crosscheck rule IDs and final rule-pair coverage valid.')
    for app in documents['index.json']['apps']:
        print(app['app_id'] + ': ' + ', '.join(f'{k}={v}' for k, v in app['counts'].items()))
    return 0


if __name__ == '__main__':
    sys.exit(main())
