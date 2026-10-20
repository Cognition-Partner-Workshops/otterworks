"""Unit tests for rates.py: t/rates.t ported, the golden rates days, and Perl FxReport::Rates side by side.

Run from fx-report/app: UV_PYTHON=3.12 uv run --no-project --with pytest==8.3.5 pytest -v
(or python3 -m unittest -v test_rates). SameAsPerl is skipped when perl is not on PATH.
"""
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

import rates

FX_REPORT = Path(__file__).resolve().parent.parent
GOLDEN = FX_REPORT / "tests" / "golden"
GOLDEN_DAYS = ("2026-10-14", "2026-10-15", "2026-10-16")
HEADER = "pair,open,high,low,close,avg_mid,ticks\n"

sys.path.insert(0, str(FX_REPORT / "tests" / "characterization"))
from report_page import parse


def rates_file(day):
    return GOLDEN / "rates" / f"rates-{day}.csv"


def report_cells(day):
    """The table cells fx-report.cgi prints for a day, from the golden rates files."""
    prev_day = (date.fromisoformat(day) - timedelta(days=1)).isoformat()
    today, prev = rates.read_day(rates_file(day)), rates.read_day(rates_file(prev_day))
    return [[r["pair"], r["close"], r["avg"], rates.format_range(r["range"]), rates.format_change(r["chg_pct"])]
            for r in rates.moves(today, prev)]


class RatesT(unittest.TestCase):
    """t/rates.t, one assertion per test."""
    def setUp(self):
        self.today = {"EURUSD": {"close": 1.1000, "high": 1.11, "low": 1.09, "avg": 1.1}}
        self.prev = {"EURUSD": {"close": 1.0000}}

    def test_one_pair(self):
        self.assertEqual(len(rates.moves(self.today, self.prev)), 1)

    def test_ten_percent_move(self):
        self.assertLess(abs(rates.moves(self.today, self.prev)[0]["chg_pct"] - 10), 1e-9)

    def test_no_previous_day_no_change(self):
        self.assertIsNone(rates.moves(self.today, None)[0]["chg_pct"])


class GoldenDays(unittest.TestCase):
    """Every cell of the golden page for each golden rates day (Perl 5.40.1 stand-in output)."""

    def check(self, day):
        golden = parse((GOLDEN / f"day-{day}.html").read_text(encoding="utf-8"))
        self.assertEqual(report_cells(day), golden.rows)

    def test_2026_10_14_no_previous_file(self):
        self.assertIsNone(rates.read_day(rates_file("2026-10-13")))
        self.check("2026-10-14")

    def test_2026_10_15(self):
        self.check("2026-10-15")

    def test_2026_10_16(self):
        self.check("2026-10-16")

    def test_close_and_avg_are_the_csv_strings(self):
        eurchf = rates.read_day(rates_file("2026-10-14"))["EURCHF"]
        self.assertEqual((eurchf["close"], eurchf["avg"]), ("0.949120", "0.950430"))

    def test_range_and_change_are_doubles(self):
        row = rates.moves(rates.read_day(rates_file("2026-10-15")), rates.read_day(rates_file("2026-10-14")))[0]
        self.assertEqual(row["range"], 0.953680 - 0.946340)
        self.assertEqual(row["chg_pct"], (0.952620 - 0.949120) / 0.949120 * 100)


class ReadDayAndMoves(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)

    def write(self, name, text):
        path = self.dir / name
        path.write_bytes(text.encode())
        return path

    def test_header_and_blank_lines_skipped(self):
        path = self.write("d.csv", "EURUSD,1,2,3,4,5,6\n\nEURCHF,1,2,3,4,5,6\n\n")
        self.assertEqual(list(rates.read_day(path)), ["EURCHF"])

    def test_columns(self):
        path = self.write("d.csv", HEADER + "EURUSD,1.090780,1.094185,1.085755,1.091730,1.090783,24")
        self.assertEqual(rates.read_day(path), {"EURUSD": {"open": "1.090780", "high": "1.094185", "low": "1.085755",
                                                           "close": "1.091730", "avg": "1.090783", "ticks": "24"}})

    def test_missing_file_is_none_header_only_is_empty(self):
        self.assertIsNone(rates.read_day(self.dir / "rates-.csv"))
        self.assertEqual(rates.read_day(self.write("h.csv", HEADER)), {})
        self.assertEqual(rates.read_day(self.write("e.csv", "")), {})

    def test_short_rows_and_last_duplicate_wins(self):
        path = self.write("d.csv", HEADER + "GBPUSD,1.25,1.27,,\nEURUSD,1,1,1,1,1,1\nEURUSD,2,2,2,2,2,2\n")
        day = rates.read_day(path)
        self.assertEqual(day["GBPUSD"], {"open": "1.25", "high": "1.27", "low": None, "close": None,
                                         "avg": None, "ticks": None})
        self.assertEqual(day["EURUSD"]["close"], "2")

    def test_pairs_sorted_and_matched_by_pair(self):
        today = {"USDJPY": {"close": "150", "high": "151", "low": "149"}, "EURUSD": {"close": "1.1", "high": "1.2",
                                                                                   "low": "1.0"}}
        prev = {"EURUSD": {"close": "1.0"}}
        rows = rates.moves(today, prev)
        self.assertEqual([r["pair"] for r in rows], ["EURUSD", "USDJPY"])
        self.assertEqual(rates.format_change(rows[0]["chg_pct"]), "+10.000%")
        self.assertIsNone(rows[1]["chg_pct"])
        self.assertEqual(rates.format_range(rows[1]["range"]), "2.00000")

    def test_perl_numification(self):
        self.assertEqual([rates.perl_num(v) for v in (None, "", "abc", " 0.5", "0.66x", "+.5e1", "-2",
                                                         "\u0661.5", "\u00a01.5", "1\u0665")],
                         [0.0, 0.0, 0.0, 0.5, 0.66, 5.0, -2.0, 0.0, 0.0, 1.0])

    def test_formats(self):
        self.assertEqual(rates.format_range(0.0084300000000001), "0.00843")
        self.assertEqual(rates.format_change(-0.0164), "-0.016%")
        self.assertEqual(rates.format_change(0.0), "+0.000%")
        self.assertEqual(rates.format_change(None), "n/a")


PERL_DUMP = r"""
use strict; use warnings; use FxReport::Rates;
my $t = FxReport::Rates::read_day($ARGV[0]);
my $p = FxReport::Rates::read_day($ARGV[1]);
print defined $t ? "today\n" : "no today\n";
exit unless $t;
for my $r (@{ FxReport::Rates::moves($t, $p) }) {
    my $c = $r->{chg_pct};
    print join("\t", $r->{pair}, $r->{close} // 'undef', $r->{avg} // 'undef', sprintf('%.17g', $r->{range}),
               defined $c ? sprintf('%.17g', $c) : 'undef', sprintf('%.5f', $r->{range}),
               defined $c ? sprintf('%+.3f%%', $c) : 'n/a'), "\n";
}
"""


def python_dump(today_path, prev_path):
    """PERL_DUMP's output, from rates.py."""
    def text(value):
        return "undef" if value is None else value

    def g17(value):
        return "undef" if value is None else "%.17g" % value  # noqa: UP031 (as in PERL_DUMP)

    today, prev = rates.read_day(today_path), rates.read_day(prev_path)
    out = ["today" if today is not None else "no today"]
    for r in rates.moves(today, prev) if today is not None else []:
        out.append("\t".join([r["pair"], text(r["close"]), text(r["avg"]), g17(r["range"]), g17(r["chg_pct"]),
                              rates.format_range(r["range"]), rates.format_change(r["chg_pct"])]))
    return ("\n".join(out) + "\n").encode("utf-8", "surrogateescape")


@unittest.skipUnless(shutil.which("perl"), "perl not on PATH")
class SameAsPerl(unittest.TestCase):
    """Runs lib/FxReport/Rates.pm and rates.py on the same files and compares every value bit for bit (%.17g)."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)

    def same(self, today_path, prev_path):
        perl = subprocess.run(["perl", "-I", str(FX_REPORT / "lib"), "-e", PERL_DUMP, str(today_path),
                               str(prev_path)], capture_output=True, check=True).stdout
        self.assertEqual(python_dump(today_path, prev_path), perl)
        return perl

    def test_golden_days(self):
        for day in GOLDEN_DAYS:
            prev_day = (date.fromisoformat(day) - timedelta(days=1)).isoformat()
            with self.subTest(day=day):
                self.assertEqual(self.same(rates_file(day), rates_file(prev_day)).count(b"\n"), 6)

    def test_edge_files(self):
        today = self.dir / "today.csv"
        today.write_bytes((HEADER + "USDJPY,150.1,150.9,149.8,150.5,150.2,24\n\n"
                           "EURUSD,1.09,1.095,1.085,1.0915,1.09,24\r\nEURUSD,1.1,1.11,1.09,1.1000,1.1,24\n\r\n"
                           "GBPUSD,1.25,1.27\nUSDCHF,0.9,\u0661.5,\u00a00.8,1\u0665,0.9,24\nAUDUSD, 0.65,0.66x,,0.655,0.654,24,extra\n,,,\n\n"
                           "EURCHF,0.95,0.96,0.94,0.951000,0.95,24").encode())
        prev = self.dir / "prev.csv"
        prev.write_bytes((HEADER + "EURUSD,1,1,1,1.0000,1,24\nEURCHF,0.9,0.9,0.9,0.949120,0.9,24\n"
                          "AUDUSD,0.6,0.6,0.6,0.650000,0.6,24\n").encode())
        header_only = self.dir / "header.csv"
        header_only.write_bytes(HEADER.encode())
        missing = self.dir / "missing.csv"
        for t, p in ((today, prev), (today, missing), (today, header_only), (header_only, prev),
                     (missing, prev), (self.dir, prev)):
            with self.subTest(today=t.name, prev=p.name):
                self.same(t, p)


if __name__ == "__main__":
    unittest.main()
