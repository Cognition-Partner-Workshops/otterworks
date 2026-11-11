"""Exercise the shell's default date with a controlled, timezone-aware clock."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class DefaultDateTest(unittest.TestCase):
    def test_midnight_boundaries_and_override(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            stub = work / "date"
            stub.write_text('''#!/usr/bin/env python3
import os, sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
args = sys.argv[1:]
if "yesterday" not in args:
    os.execv("/usr/bin/date", ["date", *args])
zone = timezone.utc if "-u" in args or "--utc" in args else ZoneInfo(os.environ["TZ"])
now = datetime.fromisoformat(os.environ["TEST_NOW"]).astimezone(zone)
print((now - timedelta(days=1)).date())
''')
            stub.chmod(0o755)
            cases = [
                ("Asia/Tokyo", "2026-11-10T02:15:00+09:00", "2026-11-08"),
                ("America/Los_Angeles", "2026-11-09T17:30:00-08:00", "2026-11-09"),
                ("UTC", "2026-11-09T23:59:59+00:00", "2026-11-08"),
                ("UTC", "2026-11-10T00:00:00+00:00", "2026-11-09"),
            ]
            for zone, now, expected in cases:
                for explicit in (False, True):
                    with self.subTest(zone=zone, now=now, explicit=explicit):
                        env = {**os.environ, "PATH": f"{work}:{os.environ['PATH']}",
                               "TZ": zone, "TEST_NOW": now, "SFTP_DRY_RUN": "1",
                               "FINANCE_WAREHOUSE_ENABLED": "true",
                               "WAREHOUSE_EXPORT_BIN": str(ROOT / "tests/fake_export.sh"),
                               "EXPORT_CAPTURE": str(work / "args"),
                               "RAW_FIXTURE": str(ROOT / "tests/fixtures/rows.csv")}
                        args = ["2026-01-05", str(work / "explicit.csv")] if explicit else []
                        subprocess.run(["bash", str(ROOT / "bin/nightly_extract.sh"), *args],
                                       cwd=work, env=env, check=True, capture_output=True)
                        actual = (work / "args").read_text().splitlines()[0]
                        self.assertEqual(actual, "2026-01-05" if explicit else expected)
                        if not explicit:
                            self.assertTrue((work / f"partner-invoices-{expected}.csv").exists())


if __name__ == "__main__":
    unittest.main()
