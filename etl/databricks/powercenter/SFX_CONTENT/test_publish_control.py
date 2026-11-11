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
                expected = publish_control.literal(json.dumps(dependencies)) + ' AS cross_folder_dependencies'
                self.assertEqual(merge.count(expected), 5)

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
