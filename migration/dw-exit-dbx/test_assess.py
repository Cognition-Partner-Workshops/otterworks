import unittest
import os
from unittest.mock import patch

from assess import area, loc, mask
import assess
from load_control import connect


class AssessmentHelpers(unittest.TestCase):
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


if __name__ == '__main__':
    unittest.main()
