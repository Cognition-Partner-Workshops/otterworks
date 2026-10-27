"""Regression tests for the merged global-fleet rule catalog checker."""
import copy
import json
import unittest
from pathlib import Path

import check_catalog


ROOT = Path(__file__).resolve().parents[4]
CATALOG_PATH = ROOT / 'industries/manufacturing/global-fleet/discovery/catalog.json'


class CatalogCheckerTests(unittest.TestCase):
    def setUp(self):
        self.catalog = json.loads(CATALOG_PATH.read_text())

    def errors(self, catalog):
        return check_catalog.check(catalog, ROOT)

    def assert_error(self, catalog, expected):
        errors = self.errors(catalog)
        self.assertTrue(
            any(expected in error for error in errors),
            f'expected {expected!r} in errors:\n' + '\n'.join(errors),
        )

    def test_real_catalog_passes(self):
        self.assertEqual(self.errors(copy.deepcopy(self.catalog)), [])

    def test_a_rule_ids_and_verdicts_are_valid(self):
        catalog = copy.deepcopy(self.catalog)
        catalog['rules'][0]['id'] = 'GF1'
        self.assert_error(catalog, 'must match GF followed by two digits')

        catalog = copy.deepcopy(self.catalog)
        catalog['rules'][1]['id'] = catalog['rules'][0]['id']
        self.assert_error(catalog, f"duplicate rule id {catalog['rules'][0]['id']}")

        catalog = copy.deepcopy(self.catalog)
        catalog['rules'][0]['verdict'] = 'unknown'
        self.assert_error(catalog, "must be one of catalog verdicts")

    def test_b_every_source_rule_id_is_covered(self):
        catalog = copy.deepcopy(self.catalog)
        source_id = 'MF-R01'
        for rule in catalog['rules']:
            rule_ids = rule.get('mainframe', {}).get('rule_ids', [])
            rule['mainframe']['rule_ids'] = [
                ident for ident in rule_ids if ident != source_id
            ]
        self.assert_error(catalog, f'coverage.mainframe.{source_id}')

    def test_b_catalog_cannot_reference_unknown_source_rule_ids(self):
        catalog = copy.deepcopy(self.catalog)
        catalog['rules'][0]['mainframe']['rule_ids'].append('MF-R999')
        self.assert_error(catalog, 'unknown source rule id MF-R999')

    def test_b_source_rule_id_cannot_repeat_within_one_catalog_rule(self):
        catalog = copy.deepcopy(self.catalog)
        rule_ids = catalog['rules'][0]['mainframe']['rule_ids']
        rule_ids.append(rule_ids[0])
        self.assert_error(catalog, f'duplicate source rule id {rule_ids[0]}')

    def test_c_one_sided_app_matches_the_rule_verdict(self):
        catalog = copy.deepcopy(self.catalog)
        rule = next(rule for rule in catalog['rules'] if rule['verdict'] == 'one-sided')
        rule['one_sided_app'] = 'unknown-app'
        self.assert_error(catalog, 'one-sided rules must name')

        catalog = copy.deepcopy(self.catalog)
        rule = next(rule for rule in catalog['rules'] if rule['verdict'] == 'differ')
        rule['one_sided_app'] = 'gf-mainframe-idms'
        self.assert_error(catalog, 'agree and differ rules must set this to null')

    def test_d_source_references_exist_and_are_in_bounds(self):
        catalog = copy.deepcopy(self.catalog)
        catalog['rules'][0]['mainframe']['sources'][0] = 'missing/source.java:1'
        self.assert_error(catalog, 'source file does not exist')

        catalog = copy.deepcopy(self.catalog)
        catalog['rules'][0]['portal']['sources'][0] = (
            'industries/manufacturing/global-fleet/jsf-portal/pom.xml:999999'
        )
        self.assert_error(catalog, 'source line outside file')

        catalog = copy.deepcopy(self.catalog)
        catalog['rules'][0]['shared_sources'] = [
            'industries/manufacturing/global-fleet/discovery/README.md:4-2'
        ]
        self.assert_error(catalog, 'source range start exceeds end')

    def test_e_each_rule_has_prefixed_tests_on_a_supported_layer(self):
        catalog = copy.deepcopy(self.catalog)
        catalog['rules'][0]['tests'] = []
        self.assert_error(catalog, 'every rule must have at least one test')

        catalog = copy.deepcopy(self.catalog)
        catalog['rules'][0]['tests'][0]['name'] = 'wrong_prefix'
        self.assert_error(catalog, 'must start with GF01_')

        catalog = copy.deepcopy(self.catalog)
        catalog['rules'][0]['tests'][0]['layer'] = 'web'
        self.assert_error(catalog, 'must be fleet-service or fleet-web')

    def test_f_decisions_match_verdict_and_link_existing_rules(self):
        catalog = copy.deepcopy(self.catalog)
        catalog['rules'][0]['decision']['status'] = 'not-required'
        self.assert_error(catalog, 'differ and one-sided rules must be decided')

        catalog = copy.deepcopy(self.catalog)
        catalog['rules'][0]['decision']['decided_on'] = '2026-02-30'
        self.assert_error(catalog, 'must be a valid YYYY-MM-DD date')

        catalog = copy.deepcopy(self.catalog)
        catalog['rules'][0]['decision']['linked_to'] = 'GF99'
        self.assert_error(catalog, "unknown rule id 'GF99'")

        catalog = copy.deepcopy(self.catalog)
        catalog['rules'][0]['decision']['open_items'] = None
        self.assert_error(catalog, 'open_items: must be a list')

    def test_g_legacy_evidence_references_exist(self):
        catalog = copy.deepcopy(self.catalog)
        catalog['rules'][0]['legacy_evidence']['jsf_replay_cases'].append(
            'missing-case'
        )
        self.assert_error(catalog, "unknown evidence id 'missing-case'")

        catalog = copy.deepcopy(self.catalog)
        catalog['rules'][0]['legacy_evidence']['mainframe_holdout_pairs'].append(
            'HP-999999'
        )
        self.assert_error(catalog, "unknown evidence id 'HP-999999'")

        catalog = copy.deepcopy(self.catalog)
        catalog['rules'][0]['legacy_evidence']['refresh_probe'] = (
            'industries/manufacturing/global-fleet/missing/SUMMARY.md'
        )
        self.assert_error(catalog, 'path does not exist')

    def test_h_profiles_and_rounding_values_are_valid(self):
        catalog = copy.deepcopy(self.catalog)
        del catalog['profiles']['de']['min_grade']
        self.assert_error(catalog, 'uk and de key sets differ')

        catalog = copy.deepcopy(self.catalog)
        catalog['profiles']['uk']['benefit_percent'] = '1.00'
        self.assert_error(
            catalog,
            'may be present only when benefit_percent_source is profile',
        )

        catalog = copy.deepcopy(self.catalog)
        catalog['profiles']['uk']['mileage_rounding'] = 'INVALID'
        self.assert_error(catalog, 'invalid java.math.RoundingMode value')


if __name__ == '__main__':
    unittest.main()
