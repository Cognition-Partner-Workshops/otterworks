#!/usr/bin/env python3
"""Check the merged global-fleet rule catalog against its sources."""
import json
import re
import sys
from datetime import date
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
CATALOG_PATH = Path('industries/manufacturing/global-fleet/discovery/catalog.json')
RULE_FILES = {
    'mainframe': Path(
        'industries/manufacturing/global-fleet/discovery/rules/gf-mainframe-idms.json'
    ),
    'portal': Path(
        'industries/manufacturing/global-fleet/discovery/rules/gf-jsf-portal.json'
    ),
}
SOURCE_REF = re.compile(r'(.+):(\d+)(?:-(\d+))?')
RULE_ID = re.compile(r'GF\d\d')
DECISION_DATE = re.compile(r'\d{4}-\d{2}-\d{2}')
ROUNDING_MODES = {
    'UP',
    'DOWN',
    'CEILING',
    'FLOOR',
    'HALF_UP',
    'HALF_DOWN',
    'HALF_EVEN',
    'UNNECESSARY',
}
ONE_SIDED_APPS = {'gf-mainframe-idms', 'gf-jsf-portal'}
TEST_LAYERS = {'fleet-service', 'fleet-web'}


def check(catalog: dict, repo_root: Path) -> list[str]:
    errors = []
    root = Path(repo_root)

    def error(where, message):
        errors.append(f'{where}: {message}')

    def load_json(relative_path, where):
        try:
            return json.loads((root / relative_path).read_text())
        except (OSError, ValueError) as exc:
            error(where, f'cannot read JSON: {exc}')
            return None

    if not isinstance(catalog, dict):
        return ['catalog: expected a JSON object']

    rules = catalog.get('rules')
    if not isinstance(rules, list):
        error('rules', 'expected a list')
        rules = []

    verdicts = catalog.get('verdicts')
    if not isinstance(verdicts, dict):
        error('verdicts', 'expected an object')
        verdicts = {}
    verdict_keys = set(verdicts)

    seen_ids = set()
    all_ids = set()
    for index, rule in enumerate(rules):
        where = f'rules[{index}]'
        if not isinstance(rule, dict):
            error(where, 'expected an object')
            continue
        ident = rule.get('id')
        if not isinstance(ident, str) or not RULE_ID.fullmatch(ident):
            error(f'{where}.id', 'must match GF followed by two digits')
        elif ident in seen_ids:
            error(f'{where}.id', f'duplicate rule id {ident}')
        if isinstance(ident, str):
            all_ids.add(ident)
            seen_ids.add(ident)

        verdict = rule.get('verdict')
        if (
            not isinstance(verdict, str)
            or verdict not in verdict_keys
            or verdict not in {'agree', 'differ', 'one-sided'}
        ):
            error(
                f'{where}.verdict',
                f'{verdict!r} must be one of catalog verdicts agree, differ, one-sided',
            )

    coverage_ids = {}
    source_rules_by_app = {}
    for app, relative_path in RULE_FILES.items():
        document = load_json(relative_path, str(relative_path))
        ids = set()
        source_rules = {}
        if isinstance(document, dict) and isinstance(document.get('rules'), list):
            for source_rule in document['rules']:
                if isinstance(source_rule, dict) and isinstance(source_rule.get('id'), str):
                    ids.add(source_rule['id'])
                    source_rules[source_rule['id']] = source_rule
        elif document is not None:
            error(str(relative_path), 'expected a rules list')
        coverage_ids[app] = ids
        source_rules_by_app[app] = source_rules

    for app in ('mainframe', 'portal'):
        referenced_ids = set()
        for index, rule in enumerate(rules):
            if not isinstance(rule, dict):
                continue
            app_data = rule.get(app)
            if not isinstance(app_data, dict):
                continue

            copied_rules = app_data.get('rules', [])
            copied_rules_where = f'rules[{index}].{app}.rules'
            if not isinstance(copied_rules, list):
                error(copied_rules_where, 'expected a list')
            else:
                for copied_index, copied_rule in enumerate(copied_rules):
                    copied_where = f'{copied_rules_where}[{copied_index}]'
                    if not isinstance(copied_rule, dict):
                        error(copied_where, 'expected an object')
                        continue
                    if 'id' not in copied_rule:
                        error(copied_where, 'copied source rule must include an id')
                        continue
                    copied_id = copied_rule['id']
                    if copied_id is None:
                        continue
                    if not isinstance(copied_id, str):
                        error(copied_where, 'copied source rule id must be a string or null')
                        continue
                    source_rule = source_rules_by_app.get(app, {}).get(copied_id)
                    if source_rule is None:
                        error(copied_where, f'unknown copied source rule id {copied_id}')
                        continue
                    for field, value in copied_rule.items():
                        if field not in source_rule or source_rule[field] != value:
                            error(
                                copied_where,
                                f'copied source rule {copied_id} field {field} does not match source',
                            )

            rule_ids = app_data.get('rule_ids', [])
            if not isinstance(rule_ids, list):
                error(f'rules[{index}].{app}.rule_ids', 'expected a list')
                continue
            rule_where = f'rules[{index}].{app}.rule_ids'
            seen_in_rule = set()
            for ident in rule_ids:
                if not isinstance(ident, str):
                    error(rule_where, f'expected a rule id string, got {ident!r}')
                    continue
                if ident in seen_in_rule:
                    error(rule_where, f'duplicate source rule id {ident}')
                seen_in_rule.add(ident)
                referenced_ids.add(ident)
                if ident not in coverage_ids.get(app, set()):
                    error(rule_where, f'unknown source rule id {ident}')
        for ident in sorted(coverage_ids.get(app, set()) - referenced_ids):
            error(
                f'coverage.{app}.{ident}',
                'source rule id is not referenced by any catalog rule',
            )

    for index, rule in enumerate(rules):
        if not isinstance(rule, dict):
            continue
        where = f'rules[{index}]'
        ident = rule.get('id')
        verdict = rule.get('verdict')
        one_sided_app = rule.get('one_sided_app')
        if verdict == 'one-sided':
            if not isinstance(one_sided_app, str) or one_sided_app not in ONE_SIDED_APPS:
                error(
                    f'{where}.one_sided_app',
                    'one-sided rules must name gf-mainframe-idms or gf-jsf-portal',
                )
        elif isinstance(verdict, str) and verdict in {'agree', 'differ'} and one_sided_app is not None:
            error(f'{where}.one_sided_app', 'agree and differ rules must set this to null')

        for app in ('mainframe', 'portal'):
            app_data = rule.get(app)
            sources = app_data.get('sources', []) if isinstance(app_data, dict) else []
            if not isinstance(sources, list):
                error(f'{where}.{app}.sources', 'expected a list')
                continue
            for source_index, source in enumerate(sources):
                source_where = f'{where}.{app}.sources[{source_index}]'
                _check_source(source, source_where, root, error)
        shared_sources = rule.get('shared_sources', [])
        if not isinstance(shared_sources, list):
            error(f'{where}.shared_sources', 'expected a list')
        else:
            for source_index, source in enumerate(shared_sources):
                source_where = f'{where}.shared_sources[{source_index}]'
                _check_source(source, source_where, root, error)

        tests = rule.get('tests')
        if not isinstance(tests, list) or not tests:
            error(f'{where}.tests', 'every rule must have at least one test')
            tests = []
        for test_index, test in enumerate(tests):
            test_where = f'{where}.tests[{test_index}]'
            if not isinstance(test, dict):
                error(test_where, 'expected an object')
                continue
            name = test.get('name')
            if not isinstance(name, str) or not isinstance(ident, str) or not name.startswith(
                f'{ident}_'
            ):
                error(test_where + '.name', f'must start with {ident}_')
            layer = test.get('layer')
            if not isinstance(layer, str) or layer not in TEST_LAYERS:
                error(test_where + '.layer', 'must be fleet-service or fleet-web')

        decision = rule.get('decision')
        if not isinstance(decision, dict):
            error(f'{where}.decision', 'expected an object')
            decision = {}
        if verdict == 'agree':
            if decision.get('status') != 'not-required':
                error(f'{where}.decision.status', 'agree rules must be not-required')
        elif isinstance(verdict, str) and verdict in {'differ', 'one-sided'}:
            if decision.get('status') != 'decided':
                error(f'{where}.decision.status', 'differ and one-sided rules must be decided')
            for field in ('option', 'decision', 'decided_by'):
                value = decision.get(field)
                if not isinstance(value, str) or not value.strip():
                    error(f'{where}.decision.{field}', 'must be a non-empty string')
            decided_on = decision.get('decided_on')
            if (
                not isinstance(decided_on, str)
                or not DECISION_DATE.fullmatch(decided_on)
                or not _valid_date(decided_on)
            ):
                error(f'{where}.decision.decided_on', 'must be a valid YYYY-MM-DD date')
            if not isinstance(decision.get('open_items'), list):
                error(f'{where}.decision.open_items', 'must be a list')
        if 'linked_to' in decision:
            linked_to = decision['linked_to']
            if not isinstance(linked_to, str) or linked_to not in all_ids:
                error(f'{where}.decision.linked_to', f'unknown rule id {linked_to!r}')

        legacy = rule.get('legacy_evidence', {})
        if not isinstance(legacy, dict):
            error(f'{where}.legacy_evidence', 'expected an object')
            legacy = {}
        _check_evidence_ids(
            legacy.get('jsf_replay_cases', []),
            Path('industries/manufacturing/global-fleet/parity/jsf/requests.json'),
            'cases',
            f'{where}.legacy_evidence.jsf_replay_cases',
            root,
            error,
        )
        _check_evidence_ids(
            legacy.get('mainframe_holdout_pairs', []),
            Path('industries/manufacturing/global-fleet/parity/mainframe/pairs.json'),
            'pairs',
            f'{where}.legacy_evidence.mainframe_holdout_pairs',
            root,
            error,
        )
        if 'refresh_probe' in legacy:
            refresh_probe = legacy['refresh_probe']
            if (
                not isinstance(refresh_probe, str)
                or Path(refresh_probe).is_absolute()
                or '..' in Path(refresh_probe).parts
                or not (root / refresh_probe).is_file()
            ):
                error(
                    f'{where}.legacy_evidence.refresh_probe',
                    f'path does not exist: {refresh_probe!r}',
                )

    _check_profiles(catalog.get('profiles'), error)
    return errors


def _check_source(source, where, root, error):
    if not isinstance(source, str):
        error(where, 'expected a path:line or path:start-end string')
        return
    match = SOURCE_REF.fullmatch(source)
    if match is None:
        error(where, f'expected a path:line or path:start-end string, got {source!r}')
        return
    path_text, start_text, end_text = match.groups()
    relative_path = Path(path_text)
    start = int(start_text)
    end = int(end_text) if end_text is not None else start
    if relative_path.is_absolute() or '..' in relative_path.parts:
        error(where, f'path must be repository-relative: {path_text}')
        return
    path = root / relative_path
    if not path.is_file():
        error(where, f'source file does not exist: {path_text}')
        return
    if start > end:
        error(where, f'source range start exceeds end: {source}')
        return
    try:
        line_count = len(path.read_text().splitlines())
    except OSError as exc:
        error(where, f'cannot read source file {path_text}: {exc}')
        return
    if start < 1 or end > line_count:
        error(where, f'source line outside file: {source} ({line_count} lines)')


def _valid_date(value):
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _check_evidence_ids(values, relative_path, list_key, where, root, error):
    if not isinstance(values, list):
        error(where, 'expected a list')
        return
    document_path = root / relative_path
    document = None
    if values:
        try:
            document = json.loads(document_path.read_text())
        except (OSError, ValueError) as exc:
            error(str(relative_path), f'cannot read JSON: {exc}')
            return
        entries = document.get(list_key) if isinstance(document, dict) else None
        if not isinstance(entries, list):
            error(str(relative_path), f'expected a {list_key} list')
            return
        known_ids = {
            item.get('id')
            for item in entries
            if isinstance(item, dict) and isinstance(item.get('id'), str)
        }
        for index, ident in enumerate(values):
            if not isinstance(ident, str) or ident not in known_ids:
                error(f'{where}[{index}]', f'unknown evidence id {ident!r}')


def _check_profiles(profiles, error):
    if not isinstance(profiles, dict):
        error('profiles', 'expected an object')
        return
    normalized = {}
    for name in ('uk', 'de'):
        profile = profiles.get(name)
        if not isinstance(profile, dict):
            error(f'profiles.{name}', 'expected an object')
            continue
        has_benefit_percent = 'benefit_percent' in profile
        if has_benefit_percent and profile.get('benefit_percent_source') != 'profile':
            error(
                f'profiles.{name}.benefit_percent',
                'may be present only when benefit_percent_source is profile',
            )
        normalized[name] = set(profile) - {'benefit_percent'}
        for key, value in profile.items():
            if key.endswith('_rounding') and (
                not isinstance(value, str) or value not in ROUNDING_MODES
            ):
                error(
                    f'profiles.{name}.{key}',
                    f'invalid java.math.RoundingMode value {value!r}',
                )
    if 'uk' in normalized and 'de' in normalized:
        uk_only = normalized['uk'] - normalized['de']
        de_only = normalized['de'] - normalized['uk']
        if uk_only or de_only:
            error(
                'profiles',
                f'uk and de key sets differ (uk-only: {sorted(uk_only)}, '
                f'de-only: {sorted(de_only)})',
            )


def main():
    try:
        catalog = json.loads((ROOT / CATALOG_PATH).read_text())
    except (OSError, ValueError) as exc:
        errors = [f'{CATALOG_PATH}: cannot read JSON: {exc}']
    else:
        errors = check(catalog, ROOT)
    if errors:
        for problem in errors:
            print(problem)
        print(f'FAIL: {len(errors)} problem(s)')
        return 1
    print('PASS: catalog rules, coverage, references, tests, decisions, evidence and profiles valid.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
