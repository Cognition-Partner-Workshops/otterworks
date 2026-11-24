import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from driver import RATING_FIELDS, compare, read_cobol


class ParityDriverTest(unittest.TestCase):
    def test_reads_total_after_nonzero_fee(self):
        rateout = (
            "P0000001" "OK " "    " "000041500" "1000" "T"
            "0000001200G" "0000001200G" "N" "03500" "0000001550G" "            "
        )
        with TemporaryDirectory() as directory:
            path = Path(directory) / "rated.dat"
            path.write_text(rateout + "\n")
            self.assertEqual(read_cobol(path)["P0000001"]["total"], 15507)

    def test_reports_a_total_only_mismatch(self):
        rating = {
            "status": "OK", "reason": "", "base": 12007, "modified": 12007,
            "minimum": "N", "source": "T",
        }
        cobol = {"P0000001": dict(rating, total=15507)}
        java = {"P0000001": dict(rating, total=15508)}

        result = compare(cobol, java, RATING_FIELDS, ("cobol", "java"))

        self.assertEqual(result["mismatched"], 1)
        self.assertEqual(result["mismatches"], [
            {"policy": "P0000001", "fields": {"total": {"cobol": 15507, "java": 15508}}},
        ])
