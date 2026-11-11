import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import collect_evidence
from dbx import ROOT
from run_validation import failed_runs


class ValidationTests(unittest.TestCase):
    def test_conversion_status_controls_board(self):
        evidence = json.loads((ROOT / 'evidence.json').read_text())
        validation = copy.deepcopy(evidence['validation'])
        for result in validation.values():
            for item in [*result['parity'], result['idempotence']]:
                item['rows'] = [item['metrics']]
        reads = {'inputs.json': evidence['inputs'], 'validation.json': validation,
                 'query-history.json': {'rows': [], 'statement_id': 'history'},
                 'oracle.json': evidence['oracle'], 'reject-parity.json': {},
                 'job-summary.json': evidence['job'], 'job-metadata.json': evidence['job_metadata']}
        mapping = 'm_SFX_STG_APP_USER'
        for runs, red in (([[{'status': {'state': 'SUCCEEDED'}}]] * 2, False),
                          ([[{'status': {'state': 'FAILED'}}]] * 2, True), ([], True),
                          ([[], []], True)):
            with self.subTest(runs=runs), tempfile.TemporaryDirectory() as directory:
                self.assertEqual(failed_runs({'runs': runs}), red)
                validation[mapping]['runs'] = runs
                root = Path(directory)
                (root / 'statements.jsonl').write_text('')
                with patch.object(collect_evidence, 'ROOT', root), patch.object(collect_evidence, 'EVIDENCE', root), patch.object(
                        collect_evidence, 'read', side_effect=lambda name: reads[name]), patch.object(
                        collect_evidence, 'read_optional', side_effect=lambda name, default: default):
                    collect_evidence.collect()
                row = next(r for r in json.loads((root / 'evidence.json').read_text())['rows'] if r['mapping'] == mapping)
                self.assertEqual(row['status'], 'red' if red else 'green')
                if red:
                    self.assertEqual(row['licence_features'], [])
                    self.assertIn('Conversion failed', row['red_reason'])
