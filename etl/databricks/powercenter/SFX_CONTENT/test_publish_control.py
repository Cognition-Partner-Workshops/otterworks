import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import publish_control
from dbx import ROOT


class PublishTests(unittest.TestCase):
    def test_preserves_dependency_evidence(self):
        evidence = json.loads((ROOT / 'evidence.json').read_text())
        for dependencies in (evidence['cross_folder_dependencies'], []):
            with self.subTest(dependencies=dependencies), tempfile.TemporaryDirectory() as directory:
                evidence['cross_folder_dependencies'] = dependencies
                root = Path(directory)
                (root / 'evidence.json').write_text(json.dumps(evidence))
                inventory = [{'source_path': row['source'], 'object_name': row['mapping']} for row in evidence['rows']]
                verified = [{'pr': 'pr', 'status': row['status']} for row in evidence['rows']]
                with patch.object(publish_control, 'ROOT', root), patch.object(publish_control, 'EVIDENCE', root), patch.object(
                        publish_control, 'rows', side_effect=lambda result: result['rows']), patch.object(
                        publish_control, 'sql', side_effect=[{'rows': [{'col_name': f} for f in publish_control.FIELDS]},
                            {'rows': inventory}, {'statement_id': 'merge', 'rows': []}, {'statement_id': 'verify', 'rows': verified}]) as sql:
                    publish_control.publish('pr')
                merge = sql.call_args_list[2].args[0]
                records = merge.split('UNION ALL')
                for row, record in zip(evidence['rows'], records):
                    own = [d for d in dependencies if row['mapping'] in [name.strip() for name in d['mapping'].split(',')]]
                    expected = publish_control.literal(json.dumps(own)) + ' AS cross_folder_dependencies'
                    self.assertIn(expected, record)

    def test_additional_red_rows_publish_and_save_evidence(self):
        evidence = json.loads((ROOT / 'evidence.json').read_text())
        for row in evidence['rows']:
            row['status'] = 'red'
            row['red_reason'] = 'Conversion failed'
            row['licence_features'] = []
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'evidence.json').write_text(json.dumps(evidence))
            inventory = [{'source_path': row['source'], 'object_name': row['mapping']} for row in evidence['rows']]
            verified = [{'pr': 'pr', 'status': row['status']} for row in evidence['rows']]
            with patch.object(publish_control, 'ROOT', root), patch.object(publish_control, 'EVIDENCE', root), patch.object(
                    publish_control, 'rows', side_effect=lambda r: r['rows']), patch.object(
                    publish_control, 'sql', side_effect=[{'rows': [{'col_name': f} for f in publish_control.FIELDS]},
                        {'rows': inventory}, {'statement_id': 'merge', 'rows': []}, {'statement_id': 'verify', 'rows': verified}]):
                publish_control.publish('pr')
            saved = json.loads((root / 'control.json').read_text())
            self.assertEqual(saved['rows'], verified)
            self.assertEqual(saved['merge_statement_id'], 'merge')

    def test_invalid_board_never_writes(self):
        evidence = json.loads((ROOT / 'evidence.json').read_text())
        for board in ([], evidence['rows'] * 2, [{**r, 'status': 'unknown'} for r in evidence['rows']]):
            with self.subTest(board=board), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / 'evidence.json').write_text(json.dumps({**evidence, 'rows': board}))
                with patch.object(publish_control, 'ROOT', root), patch.object(publish_control, 'sql') as sql:
                    with self.assertRaisesRegex(ValueError, 'five unique mapping rows'):
                        publish_control.publish('pr')
                    sql.assert_not_called()

    def test_missing_dependencies_refuses_publish(self):
        evidence = json.loads((ROOT / 'evidence.json').read_text())
        del evidence['cross_folder_dependencies']
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'evidence.json').write_text(json.dumps(evidence))
            inventory = [{'source_path': row['source'], 'object_name': row['mapping']} for row in evidence['rows']]
            with patch.object(publish_control, 'ROOT', root), patch.object(publish_control, 'rows', side_effect=lambda r: r), patch.object(
                    publish_control, 'sql', side_effect=[[{'col_name': f} for f in publish_control.FIELDS], inventory]) as sql:
                with self.assertRaises(KeyError):
                    publish_control.publish('pr')
                self.assertEqual(sql.call_count, 2)
