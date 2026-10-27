"""Regression tests for source validation and final crosscheck coverage."""
import contextlib
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import validate


class ValidatorTests(unittest.TestCase):
    def setUp(self):
        self.data = {
            p.relative_to(validate.HERE).as_posix(): json.loads(p.read_text())
            for p in validate.HERE.rglob('*.json')
        }

    def problems(self, raw_files=None):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            for name, document in self.data.items():
                path = directory / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(document))
            for name, text in (raw_files or {}).items():
                (directory / name).write_text(text)
            return validate.validate(directory, validate.ROOT)[0]

    def assert_problem(self, text):
        self.assertTrue(any(text in p for p in self.problems()), text)

    def test_published_data(self):
        self.assertEqual(self.problems(), [])

    def test_empty_final_pairs_cannot_use_history_or_prose_as_coverage(self):
        self.data['crosscheck.json']['rule_pairs'] = []
        problems = self.problems()
        for name, document in self.data.items():
            if not name.startswith('rules/'):
                continue
            for rule in document.get('rules', []):
                self.assertIn(
                    f"crosscheck.json: rule id absent from final rule_pairs: {rule['id']}",
                    problems,
                )

    def test_mileage_rule_missing_from_final_pair(self):
        for pair in self.data['crosscheck.json']['rule_pairs']:
            pair['portal_rule_ids'] = [
                ident for ident in pair['portal_rule_ids'] if ident != 'JP-R32'
            ]
        self.assert_problem('rule id absent from final rule_pairs: JP-R32')

    def test_missing_crosscheck(self):
        del self.data['crosscheck.json']
        self.assert_problem('rule id absent from final rule_pairs: JP-R32')

    def test_undefined_crosscheck_rule(self):
        self.data['crosscheck.json']['rule_pairs'][0]['portal_rule_ids'].append('JP-R999')
        self.assert_problem('undefined rule id JP-R999')

    def test_no_json(self):
        self.data = {}
        self.assert_problem('no JSON data files')

    def test_invalid_json(self):
        self.assertTrue(any('invalid JSON' in p for p in self.problems({'broken.json': '{'})))

    def test_rules_and_questions_need_sources(self):
        for kind in ('rules', 'navigation_questions'):
            with self.subTest(kind=kind):
                item = self.data['rules/gf-jsf-portal.json'][kind][0]
                sources = item.pop('sources')
                self.assert_problem('no source')
                item['sources'] = sources

    def test_source_file_and_bounds(self):
        rule = self.data['rules/gf-jsf-portal.json']['rules'][0]
        rule['sources'] = [validate.PREFIX + 'missing.java:1']
        self.assert_problem('source file does not exist')
        rule['sources'] = [validate.PREFIX + 'ESTATE.md:0-99999']
        self.assert_problem('line range outside file')

    def test_duplicate_rule_and_question_ids(self):
        for kind in ('rules', 'navigation_questions'):
            with self.subTest(kind=kind):
                items = self.data['rules/gf-jsf-portal.json'][kind]
                items.append(copy.deepcopy(items[0]))
                self.assert_problem(f'duplicate {kind} id')
                items.pop()

    def test_evidence_must_match_in_order(self):
        rule = self.data['rules/gf-jsf-portal.json']['rules'][0]
        for evidence in ('not in the source', ' ... ', 'finally ... EntityManager em'):
            with self.subTest(evidence=evidence):
                rule['evidence'] = evidence
                self.assert_problem('evidence not found')

    def test_short_reference_rejected(self):
        self.data['rules/gf-jsf-portal.json']['rules'][0]['sources'] = ['FleetService.java:1']
        self.assert_problem('non-canonical source reference')

    def test_main_lists_problems_and_exits_one(self):
        with patch.object(validate, 'validate', return_value=(['first', 'second'], {})):
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(validate.main(), 1)
        self.assertEqual(output.getvalue(), 'first\nsecond\nFAIL: 2 problem(s)\n')


if __name__ == '__main__':
    unittest.main()
