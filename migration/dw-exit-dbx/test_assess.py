import unittest
import os
import copy
import subprocess
from unittest.mock import patch, MagicMock

from assess import area, loc, mask
import assess
from check import live_differences, manifest_differences
from load_control import connect
import load_control


class AssessmentHelpers(unittest.TestCase):
    def test_xml_parsing(self):
        text = '<!DOCTYPE POWERMART SYSTEM "powrmart.dtd"><POWERMART><SOURCE NAME="EXAMPLE"/></POWERMART>'
        self.assertEqual(assess.parse_xml(text).find('SOURCE').attrib['NAME'], 'EXAMPLE')
        with self.assertRaises(assess.ET.ParseError):
            assess.parse_xml('')
        with self.assertRaisesRegex(ValueError, 'entity declarations'):
            assess.parse_xml('<!DOCTYPE root [<!ENTITY example "value">]><root>&example;</root>')
        with self.assertRaises(assess.ET.ParseError):
            assess.parse_xml('<root>')

    def test_sql_tag_and_bound_values(self):
        cursor = MagicMock()
        values = ["example'); DROP TABLE example; --"]
        load_control.execute(cursor, 'check', 'SELECT ?', values)
        cursor.execute.assert_called_once_with('/* run=dbx-d1111 act=assess step=check */ SELECT ?', values)
        for step in ('', 'check */ DELETE FROM example; /*'):
            with self.assertRaises(ValueError):
                load_control.execute(cursor, step, 'SELECT 1')
        self.assertEqual(cursor.execute.call_count, 1)

    def test_loc(self):
        self.assertEqual(loc('-- comment\nSELECT 1;\n/* block\ncomment */\n'), 1)

    def test_empty(self):
        self.assertEqual(loc(''), 0)
        self.assertEqual(mask(''), '')
        self.assertEqual(area('unknown'), 'data-platform')

    def test_privacy(self):
        self.assertEqual(mask('FIN_ANALYST_' + 'J' + 'EXAMPLE'), 'FIN_ANALYST_J*****')
        self.assertEqual(mask('nb_dsci_' + 'p' + 'example'), 'nb_dsci_p*****')
        self.assertEqual(mask('svc_etl_audit'), 'svc_etl_audit')

    def test_catalog_rejected(self):
        with patch.dict(os.environ, {'DATABRICKS_CATALOG': 'other'}):
            with self.assertRaisesRegex(ValueError, 'Only catalog cpw'):
                connect()

    def test_code_reader_and_writer(self):
        path = 'warehouse/teradata/macros/example.sql'
        with patch.object(assess, 'source_files', return_value=[path]), patch.object(assess, 'spark_files', return_value=[]), patch.object(assess, 'git', return_value=''), patch.object(assess, 'read', return_value='INSERT INTO SFX_AUDIT.LEGAL_HOLD SELECT * FROM SFX_AUDIT.ACCESS_REVIEW;'):
            readers = assess.code_readers(['SFX_AUDIT.LEGAL_HOLD', 'SFX_AUDIT.ACCESS_REVIEW'])
        self.assertEqual(readers['SFX_AUDIT.LEGAL_HOLD'], [])
        self.assertEqual(readers['SFX_AUDIT.ACCESS_REVIEW'], [path])

    def test_no_reader_sources(self):
        with patch.object(assess, 'source_files', return_value=[]), patch.object(assess, 'spark_files', return_value=[]), patch.object(assess, 'git', return_value=''):
            self.assertEqual(assess.code_readers(['SFX_AUDIT.LEGAL_HOLD']), {'SFX_AUDIT.LEGAL_HOLD': []})

    def test_spark_landing_reader(self):
        path = 'etl/spark/jobs/py/example.py'
        with patch.object(assess, 'source_files', return_value=[]), patch.object(assess, 'spark_files', return_value=[path]), patch.object(assess, 'git', return_value=''), patch.object(assess, 'read', return_value='result = landing(spark, "USER_PREF")'):
            self.assertEqual(assess.code_readers(['SFX_USERS.USER_PREF']), {'SFX_USERS.USER_PREF': [path]})

    def test_spark_subject(self):
        with patch.object(assess, 'landing_areas', return_value={'SECURITY_ALERT': 'audit', 'DOCUMENT': 'documents'}):
            self.assertEqual(assess.spark_subject('landing(spark, "SECURITY_ALERT")'), 'audit')
            self.assertEqual(assess.spark_subject('register(spark, "SECURITY_ALERT", "DOCUMENT")'), 'data-platform')
            with self.assertRaisesRegex(ValueError, 'no grounded'):
                assess.spark_subject('')

    def test_live_field_parity(self):
        entry = dict(id='alert', target='PySpark job', wave=3, owner='@otterworks/audit', risk='medium')
        self.assertEqual(live_differences([entry], [('alert', 'PySpark job', 3, '@otterworks/audit', 'medium')]), [])
        self.assertEqual(live_differences([entry], [('alert', 'retire', 3, '@otterworks/audit', 'medium')]), ['alert'])
        self.assertEqual(live_differences([entry], []), ['alert'])
        self.assertEqual(live_differences([], []), [])

    def test_spark_lineage(self):
        with patch.object(assess, 'landing_areas', return_value={'SEARCH_INDEX_LOG': 'documents'}), patch.object(assess, 'source_files', return_value=[]):
            text = 'landing(spark, "SEARCH_INDEX_LOG").withColumn("PARSED_ACTION", col("RAW_LINE"))\nsave(frame.coalesce(2), "documents", "parsed")'
            self.assertEqual(assess.spark_io(text), (['SEARCH_INDEX_LOG'], ['/opt/lake/documents/parsed']))
            self.assertEqual(assess.spark_io(''), ([], []))
            self.assertEqual(assess.spark_io('landing(spark, "UNKNOWN_TABLE")'), ([], []))

    def test_working_tree_provenance(self):
        recorded = {'metadata': {'spark_ref': 'working tree', 'spark_commit': 'a' * 40}, 'objects': []}
        expected = copy.deepcopy(recorded)
        expected['metadata']['spark_commit'] = 'b' * 40
        with patch.object(assess, 'source_files', return_value=[]), patch.object(assess, 'spark_files', return_value=[]), patch.object(assess, 'git', return_value=''):
            self.assertEqual(manifest_differences(recorded, expected), [])
            expected['objects'] = [{'source_paths': ['source.py'], 'owner': 'changed'}]
            self.assertIn('manifest fields differ from regenerated estate assessment', manifest_differences(recorded, expected))
        with patch.object(assess, 'source_files', return_value=[]), patch.object(assess, 'spark_files', return_value=[]), patch.object(assess, 'git', side_effect=['', 'source.py']):
            self.assertIn('working-tree assessed sources changed since recorded commit', manifest_differences(recorded, expected))
        with patch.object(assess, 'source_files', return_value=[]), patch.object(assess, 'spark_files', return_value=[]), patch.object(assess, 'git', side_effect=subprocess.CalledProcessError(1, 'git')):
            self.assertIn('working-tree provenance commit does not exist or is invalid', manifest_differences(recorded, expected))

    def test_pinned_provenance_is_exact(self):
        recorded = {'metadata': {'spark_ref': 'pr-2740', 'spark_commit': 'a' * 40}, 'objects': []}
        expected = copy.deepcopy(recorded)
        expected['metadata']['spark_commit'] = 'b' * 40
        self.assertTrue(manifest_differences(recorded, expected))

    def test_physical_lineage_identity(self):
        path = '/opt/lake/audit/audit_daily_summary'
        self.assertEqual(assess.lineage_node(path, 'audit'), assess.lineage_node(path, 'data-platform'))
        self.assertNotEqual(assess.lineage_node(path, 'audit'), assess.lineage_node(path + '_other', 'audit'))
        self.assertTrue(assess.lineage_node(path, 'audit').startswith('d'))

    def test_loader_preserves_demo_fields_and_rows(self):
        with patch.object(load_control, 'connect', return_value=MagicMock()), patch.object(load_control, 'execute', return_value=MagicMock()) as execute:
            load_control.main()
        statement = next(call.args[2] for call in execute.call_args_list if call.args[1] == 'load')
        matched = statement.split('WHEN MATCHED THEN UPDATE SET ')[1].split(' WHEN NOT MATCHED')[0]
        for field in ('status', 'parity', 'pr', 'updated_at'):
            self.assertNotIn('t.' + field + '=', matched)
        self.assertNotIn('DELETE', statement)
        self.assertNotIn('NOT MATCHED BY SOURCE', statement)


if __name__ == '__main__':
    unittest.main()
