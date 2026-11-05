"""The pure record/report functions reproduce the legacy awk and Perl byte for byte.

These run the real legacy scripts from etl/legacy-extra/jobs against crafted
lines that go beyond what the parity fixtures contain.
"""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from custbill_spark.parse import legacy_psv, record_kind, trailer_count
from custbill_spark.report import render, split_record, perl_decimal
from custbill_spark.support import encode_lines, split_lines

LEGACY = Path(__file__).resolve().parents[2] / "legacy-extra"
GOOD = "CUST000001" + "Acme Widgets".ljust(30) + "20240131" + "000000123456" + "USD" + "01"
LINES = [
    GOOD,
    "CUST000002" + "Trailing   ".ljust(30) + "20240229" + "000000000001" + "EUR" + "02",
    "CUST000003" + "Short record",
    GOOD + "EXTRA BYTES BEYOND 65",
    "CUST000005" + "Non numeric amount".ljust(30) + "2024XX31" + "12AB56789012" + "GBP" + "99",
    "CUST000006" + "Leading blank amount".ljust(30) + "20240101" + "   123456789" + "USD" + "01",
    "CUST000007" + "Decimal amount".ljust(30) + "20240101" + "   .5       " + "USD" + "01",
    "CUST000008" + "Exponent amount".ljust(30) + "20240101" + "1e3         " + "USD" + "01",
    "CUST000009" + "Carriage return".ljust(30) + "20240101" + "000000000100" + "USD" + "01\r",
    "",
    "          " + " " * 30 + "        " + "            " + "   " + "  ",
    "CUST000011" + "Latin-1 caf\xe9".ljust(30) + "20240101" + "000000000100" + "USD" + "01",
    "CUST000012" + "Tab\tinside".ljust(30) + "20240101" + "000000000100" + "USD" + "01",
    "HDRCUSTBILL20240131",
    "TRL0000000012",
]


def legacy_env(root):
    return dict(os.environ, OTTERWORKS_LEGACY_ROOT=str(root), LC_ALL="C", TZ="UTC")


class ParseEquivalence(unittest.TestCase):
    def test_body_lines_match_awk(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "incoming").mkdir()
            (root / "incoming/CUSTBILL_T.dat").write_bytes(encode_lines(LINES))
            subprocess.run(["bash", str(LEGACY / "jobs/parse_custbill_fixedwidth.sh")], check=True,
                           env=legacy_env(root), capture_output=True)
            expected = split_lines((root / "parsed/CUSTBILL_T.psv").read_bytes())
        ours = [legacy_psv(line) for line in LINES if record_kind(line) == "BODY"]
        self.assertEqual(ours, expected)

    def test_unterminated_last_line_counts(self):
        self.assertEqual(split_lines(b"a\nb"), ["a", "b"])
        self.assertEqual(split_lines(b"a\nb\n"), ["a", "b"])
        self.assertEqual(split_lines(b""), [])
        self.assertEqual(split_lines(b"\n"), [""])

    def test_trailer_count(self):
        self.assertEqual(trailer_count("TRL0000000099"), 99)
        self.assertEqual(trailer_count("TRLjunk"), 0)


RECORDS = [
    "C1|Acme|2024-01-31|1234.56|USD|01",
    "C2|Beta|2024-01-31|10.00|USD|02",
    "C3|Gamma|2024-01-31|0.01|EUR|01",
    "|Blank customer|2024-01-31|99.00|USD|01",
    "C5|Unknown type|2024-01-31|5.00|USD|99",
    "C6|Missing fields|2024-01-31",
    "C7|Weird amount|2024-01-31| 7abc|GBP|01",
    "C8|Exponent|2024-01-31|1e2|GBP|01",
    "C9|Negative|2024-01-31|-3.50|GBP|02",
    "C10|Too many|2024-01-31|1.00|USD|01|extra|fields",
    "C11|Big|2024-01-31|9999999999.99|JPY|01",
    "C12|Big|2024-01-31|9999999999.99|JPY|01",
]


class ReportEquivalence(unittest.TestCase):
    def test_report_matches_perl(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "parsed").mkdir()
            (root / "parsed/CUSTBILL_T.psv").write_bytes(encode_lines(RECORDS))
            subprocess.run(["perl", str(LEGACY / "jobs/finance_excel_report.pl")], check=True,
                           env=legacy_env(root), capture_output=True)
            expected = next((root / "reports").glob("finance_billing_*.csv")).read_bytes()
        groups = {}
        for line in RECORDS:
            cust, _, _, amount, currency, rtype = split_record(line)[:6]
            if cust == "":
                continue
            count, total = groups.get((currency, rtype), (0, 0))
            groups[(currency, rtype)] = (count + 1, total + perl_decimal(amount))
        rows = sorted(((c, r, n, t) for (c, r), (n, t) in groups.items()), key=lambda g: f"{g[0]}|{g[1]}")
        self.assertEqual(render(rows), expected)


if __name__ == "__main__":
    unittest.main()
