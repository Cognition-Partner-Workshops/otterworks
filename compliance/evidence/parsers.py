"""Offline parsers for security exception and workflow evidence."""

import fnmatch
import re
from datetime import date

import yaml


def reason_exists(text):
    text = re.sub(r'Revisit by \d{4}-\d{2}-\d{2}|exp:\S+', '', text, flags=re.I)
    text = re.sub(r'Each entry carries.*', '', text, flags=re.I)
    return bool(re.search(
        r'requir|because|\bno\b|\bnot\b|intentional|fixture|lab\b|mock|test data|'
        r'by design|duplicate|gated by|informational|exempt|doesn.t|only|uses|'
        r'cannot|can.t|temporary|reason\s*:', text, re.I))


def exception(identifier, path, line, comment='', revisit=None, security=True):
    dates = re.findall(r'(?:exp:|Revisit by\s+)(\d{4}-\d{2}-\d{2})',
                       comment, re.I)
    revisit = revisit or (dates[-1] if dates else None)
    flags = []
    has_reason = reason_exists(comment)
    if security:
        if not has_reason:
            flags.append('NO_REASON')
        if not revisit:
            flags.append('NO_REVISIT_DATE')
        if re.search(r'\bQ[1-4]\b', comment, re.I) and not revisit:
            flags.append('VAGUE_DATE')
        if revisit:
            try:
                if date.fromisoformat(revisit) < date.today():
                    flags.append('EXPIRED')
            except ValueError:
                flags.append('INVALID_DATE')
    return {'id': identifier, 'path': path, 'line': line, 'comment_block': comment,
            'has_reason': has_reason, 'revisit_date': revisit, 'flags': flags,
            'security': security, 'live': 'not checked', 'findings': []}


def parse_trivyignore(text, path='.trivyignore'):
    result, section, pending = [], '', []
    per_entry_reason = False
    section_claim = ''
    for number, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if not stripped:
            pending = []
            continue
        if stripped.startswith('#'):
            comment = stripped.lstrip('# ').strip()
            if comment.startswith('---') or re.match(r'(Bulk ignore|Low-priority)', comment):
                section, pending = comment, []
                per_entry_reason = False
                section_claim = ''
            else:
                pending.append(comment)
                if re.search(r'Each entry carries.*reason', comment, re.I):
                    per_entry_reason = True
                    section_claim = comment
            continue
        fields = stripped.split()
        comments = '\n'.join(dict.fromkeys([section, section_claim, *pending])).strip()
        exp = next((field[4:] for field in fields[1:] if field.startswith('exp:')), None)
        row = exception(fields[0], path, number, comments, exp)
        row['section_claim'] = section_claim or None
        if per_entry_reason and not reason_exists('\n'.join(pending)):
            row['has_reason'] = False
            if 'NO_REASON' not in row['flags']:
                row['flags'].append('NO_REASON')
        row['glob'] = any(char in fields[0] for char in '*?[')
        if row['glob']:
            row['flags'].append('GLOB_INEFFECTIVE')
        result.append(row)
        pending = []
    return result


def parse_commented_list(text, path):
    rows, pending = [], []
    last_was_entry = False
    for number, line in enumerate(text.splitlines(), 1):
        if line.startswith('#'):
            if last_was_entry:
                pending = []
            pending.append(line.lstrip('# '))
            last_was_entry = False
        elif line.strip():
            rows.append(exception(line.strip(), path, number, '\n'.join(pending)))
            last_was_entry = True
    return rows


def parse_nosemgrep(text, path):
    rows = []
    lines = text.splitlines()
    for index, line in enumerate(lines):
        match = re.search(r'(?:#|//|--|/\*)\s*nosemgrep\b(?::\s*([^;]+))?', line)
        if not match:
            continue
        raw = (match[1] or '').rstrip(' */')
        rules = re.findall(r'[\w-]+(?:\.[\w-]+)+', raw) or ['ALL-RULES']
        preceding = []
        for previous in reversed(lines[max(0, index - 6):index]):
            if re.match(r'^\s*(#|//|--|\*|/\*)', previous):
                preceding.insert(0, re.sub(r'^\s*(#|//|--|\*|/\*)\s*', '', previous))
            else:
                break
        explanation = re.split(r'\s+(?:--|#|//)\s*', raw, maxsplit=1)
        if len(explanation) > 1:
            preceding.append(explanation[1])
        for rule in rules:
            rows.append(exception(rule, path, index + 1, '\n'.join(preceding)))
    return rows


def branch_matches(branch, patterns):
    if not patterns:
        return True
    match = False
    for pattern in patterns:
        negative = pattern.startswith('!')
        if fnmatch.fnmatchcase(branch, pattern.lstrip('!')):
            match = not negative
    return match


def event_condition(condition, event):
    """Conservative event-only filter; other expressions remain conditional."""
    if not condition:
        return 'eligible'
    checks = re.findall(r"github.event_name\s*(==|!=)\s*['\"]([^'\"]+)['\"]", condition)
    if not checks:
        return 'conditional (job if)'
    results = [(event == name) if op == '==' else (event != name) for op, name in checks]
    if ('||' in condition and not any(results)) or ('||' not in condition and not all(results)):
        return 'no (job event condition)'
    extra = re.sub(r"github.event_name\s*(==|!=)\s*['\"][^'\"]+['\"]", '', condition)
    extra = re.sub(r'[\s()|&${}]', '', extra)
    return 'conditional (job if)' if extra else 'eligible'


def parse_workflow(text, job_name, branch, step_name=None):
    data = yaml.safe_load(text) or {}
    triggers = data.get('on', data.get(True, {}))
    if isinstance(triggers, str):
        triggers = {triggers: {}}
    if isinstance(triggers, list):
        triggers = dict.fromkeys(triggers)
    jobs = data.get('jobs', {})
    if job_name not in jobs:
        raise ValueError(f'Workflow job not found: {job_name}')
    job = jobs[job_name]
    events = {}
    for event in ['push', 'pull_request']:
        config = triggers.get(event) or {}
        if event not in triggers:
            events[event] = 'no (event absent)'
        elif not branch_matches(branch, config.get('branches')) or (
                config.get('branches-ignore') and branch_matches(branch, config['branches-ignore'])):
            events[event] = 'no (branch filter)'
        else:
            state = event_condition(str(job.get('if', '')), event)
            if config.get('paths') or config.get('paths-ignore'):
                state += '; path-filtered'
            events[event] = state
    steps = job.get('steps', [])
    selected = [s for s in steps if s.get('name') == step_name] if step_name else steps
    if step_name and not selected:
        raise ValueError(f'Workflow step not found: {step_name}')
    observations = []
    for step in selected:
        script = step.get('run', '')
        markers = []
        if step.get('continue-on-error'):
            markers.append('continue-on-error')
        for token in ['|| true', 'set +e', '::warning::']:
            if token in script:
                markers.append(token)
        if markers:
            observations.append({'step': step.get('name', step.get('uses', 'unnamed')),
                                 'markers': markers, 'if': step.get('if')})
    scripts = '\n'.join(s.get('run', '') for s in selected)
    explicit_failure = False
    for step in selected:
        errexit = True
        for line in step.get('run', '').splitlines():
            if line.lstrip().startswith('#'):
                continue
            if 'set +e' in line:
                errexit = False
            if 'set -e' in line:
                errexit = True
            if step.get('continue-on-error'):
                continue
            if re.search(r'^\s*exit\s+(?!0\b)\S+', line) or (
                    errexit and '|| true' not in line and re.search(r'--error\b|--exit-code\s+1', line)):
                explicit_failure = True
    codeql = any('github/codeql-action/analyze' in s.get('uses', '') for s in selected)
    sonar_status_only = 'gate_failed=' in scripts and not explicit_failure
    if job.get('continue-on-error') or codeql or sonar_status_only:
        enforcement = 'informational findings (execution may still fail)'
    elif observations and not explicit_failure:
        enforcement = 'informational / fail-open signals; review scripts'
    elif observations:
        enforcement = 'blocking with conditional/fail-open signals; review scripts'
    else:
        enforcement = 'blocking on command failure; finding threshold requires tool configuration'
    return {'triggers': triggers, 'job_if': job.get('if'), 'events': events,
            'enforcement': enforcement, 'signals': observations,
            'job_continue_on_error': job.get('continue-on-error', False)}


def runtime_images(files):
    rows = []
    for path, text in files:
        args, stages, final = {}, {}, None
        for line in text.splitlines():
            arg = re.match(r'\s*ARG\s+(\w+)(?:=(.*))?$', line, re.I)
            if arg and arg[2] is not None:
                args[arg[1]] = arg[2].strip('"\'')
            match = re.match(r'\s*FROM\s+(?:--platform=\S+\s+)?(\S+)(?:\s+AS\s+(\S+))?', line, re.I)
            if not match:
                continue
            image = re.sub(r'\$\{(\w+)\}|\$(\w+)',
                           lambda m: args.get(m[1] or m[2], m[0]), match[1])
            final = stages.get(image.lower(), image)
            if match[2]:
                stages[match[2].lower()] = final
        if final:
            rows.append({'dockerfile': path, 'image': final,
                         'key': re.sub(r'[^\w.-]', '-', final), 'resolved': '$' not in final})
    return rows
