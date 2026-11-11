import unittest
import os
from unittest.mock import patch

from assess import area, loc, mask
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


if __name__ == '__main__':
    unittest.main()
