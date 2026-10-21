"""Unit tests for server.py: the handler over real HTTP against the golden pages, day handling, the user header,
escaping, caching, /health, the previous-close-0 failure, logging, and `python server.py` with env config.

Run from fx-report/app: UV_PYTHON=3.12 uv run --no-project --with pytest==8.3.5 pytest -v
(or python3 -m unittest -v test_server). PreviousDaySameAsPerl is skipped when perl is not on PATH.
"""
import io
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import server

APP = Path(__file__).resolve().parent
GOLDEN = APP.parent / "tests" / "golden"
HEADER = "pair,open,high,low,close,avg_mid,ticks\n"


def golden(name):
    return (GOLDEN / f"{name}.html").read_bytes()


def yesterday_utc():
    return (datetime.now(ZoneInfo("UTC")) - timedelta(days=1)).strftime("%Y-%m-%d")


class Running:
    """A ReportServer on a free port in a thread, logging to a StringIO."""

    def __init__(self, rates_dir):
        self.log = io.StringIO()
        self.httpd = server.ReportServer(("127.0.0.1", 0), str(rates_dir), self.log)
        self.base = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        self.thread = threading.Thread(target=self.httpd.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
        self.thread.start()

    def get(self, path, headers=None, method="GET"):
        req = urllib.request.Request(self.base + path, headers=headers or {}, method=method)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status, resp.headers, resp.read()
        except urllib.error.HTTPError as err:
            return err.code, err.headers, err.read()

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()


class ServerTestCase(unittest.TestCase):
    rates = {}  # extra rates files: day -> content

    def setUp(self):
        self._tz = os.environ.get("TZ")
        os.environ["TZ"] = "UTC"
        time.tzset()
        self.dir = Path(tempfile.mkdtemp())
        for f in (GOLDEN / "rates").glob("*.csv"):
            shutil.copy(f, self.dir)
        for day, content in self.rates.items():
            (self.dir / f"rates-{day}.csv").write_text(content)
        self.srv = Running(self.dir)

    def tearDown(self):
        self.srv.stop()
        shutil.rmtree(self.dir)
        if self._tz is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = self._tz
        time.tzset()

    def body(self, path, **kw):
        status, _, body = self.srv.get(path, **kw)
        self.assertEqual(status, 200)
        return body


class GoldenPages(ServerTestCase):
    def test_golden_days_byte_identical(self):
        for day in ("2026-10-14", "2026-10-15", "2026-10-16", "2026-10-17", "foo"):
            with self.subTest(day=day):
                self.assertEqual(self.body(f"/fx/fx-report.cgi?day={day}"), golden(f"day-{day}"))

    def test_root_serves_the_same_page(self):
        self.assertEqual(self.body("/?day=2026-10-15"), golden("day-2026-10-15"))

    def test_no_day_is_yesterday(self):
        for path in ("/fx/fx-report.cgi", "/"):
            with self.subTest(path=path):
                expected = golden("no-day").replace(b"2026-10-19", yesterday_utc().encode())
                self.assertEqual(self.body(path), expected)

    def test_headers(self):
        status, headers, _ = self.srv.get("/fx/fx-report.cgi?day=2026-10-15")
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "text/html; charset=utf-8")
        self.assertEqual(headers["Cache-Control"], "max-age=3600")

    def test_head_has_headers_and_no_body(self):
        status, headers, body = self.srv.get("/fx/fx-report.cgi?day=2026-10-15", method="HEAD")
        self.assertEqual((status, body), (200, b""))
        self.assertEqual(headers["Content-Length"], str(len(golden("day-2026-10-15"))))


class DayHandling(ServerTestCase):
    def assertSamePage(self, query, golden_name):
        self.assertEqual(self.body(f"/fx/fx-report.cgi{query}"), golden(golden_name))

    def test_false_day_is_yesterday(self):
        expected = golden("no-day").replace(b"2026-10-19", yesterday_utc().encode())
        for query in ("?day=", "?day=0", "?day", "?other=1", "?day=&day=2026-10-15"):
            with self.subTest(query=query):
                self.assertEqual(self.body(f"/fx/fx-report.cgi{query}"), expected)

    def test_invalid_day_is_empty(self):
        for query in ("?day=2026-10-1", "?day=2026-10-150", "?day=x2026-10-15", "?day=2026/10/15",
                      "?day=%D9%A2%D9%A0%D9%A2%D9%A6-10-15", "?day=00"):
            with self.subTest(query=query):
                self.assertSamePage(query, "day-foo")

    def test_cgi_pm_query_parsing(self):
        for query in ("?day=2026-10-15&day=2026-10-16", "?x=1;day=2026-10-15", "?day=2026-10-15;x=1",
                      "?d%61y=2026%2D10%2D15", "?day=2026-10-15&"):
            with self.subTest(query=query):
                self.assertSamePage(query, "day-2026-10-15")

    def test_trailing_newline_passes_the_check_like_perl(self):
        body = self.body("/fx/fx-report.cgi?day=2026-10-15%0A")
        self.assertIn(b"<title>FX desk report 2026-10-15\n</title>", body)
        self.assertIn(b"No rates file for this day yet.", body)  # rates-2026-10-15\n.csv does not exist

    def test_previous_day_carries_over(self):
        cases = {"2026-10-15": "2026-10-14", "2026-10-01": "2026-09-30", "2026-01-01": "2025-12-31",
                 "2024-03-01": "2024-02-29", "2026-03-01": "2026-02-28", "2026-13-05": "2027-01-04",
                 "2026-00-10": "2025-12-09", "2026-10-00": "2026-09-29", "2026-02-99": "2026-05-09",
                 "0999-03-01": "999-02-28", "9999-12-32": "9999-12-31"}
        for day, prev in cases.items():
            with self.subTest(day=day):
                self.assertEqual(server.previous_day(day), prev)

    def test_yesterday_uses_tz(self):
        now = datetime(2026, 10, 20, 23, 30, tzinfo=ZoneInfo("UTC")).timestamp()
        for tz, expected in (("UTC", "2026-10-19"), ("Pacific/Kiritimati", "2026-10-20"),
                             ("America/Los_Angeles", "2026-10-19")):
            with self.subTest(tz=tz):
                os.environ["TZ"] = tz
                time.tzset()
                self.assertEqual(server.report_day(None, now), expected)


@unittest.skipUnless(shutil.which("perl"), "perl not on PATH")
class PreviousDaySameAsPerl(unittest.TestCase):
    """previous_day against the CGI's own POSIX::strftime line (POSIX is core Perl)."""

    def test_same_as_perl(self):
        days = [f"{y:04d}-{m:02d}-{d:02d}" for y in (999, 1900, 2000, 2024, 2026, 2100) for m in range(0, 14)
                for d in (0, 1, 2, 28, 29, 30, 31, 32, 99)]
        script = ("use POSIX qw(strftime); while (my $day = <STDIN>) { chomp $day; my ($y,$m,$d) = split /-/, $day;"
                  " print strftime('%Y-%m-%d', 0, 0, 12, $d - 1, $m - 1, $y - 1900), qq{\\n} }")
        out = subprocess.run(["perl", "-e", script], input="\n".join(days) + "\n", capture_output=True,
                             text=True, check=True, env={**os.environ, "TZ": "UTC"}).stdout.splitlines()
        self.assertEqual([server.previous_day(d) for d in days], out)


class UserAndEscaping(ServerTestCase):
    rates = {"2030-01-05": HEADER + "<b>&\"'</b>,1,1.2,1.1,<i>,\"x\",3\n"}

    def test_user_header(self):
        body = self.body("/fx/fx-report.cgi?day=2026-10-15", headers={"X-Auth-Request-User": "jdoe"})
        self.assertEqual(body, golden("day-2026-10-15").replace(b"user unknown", b"user jdoe"))

    def test_user_unknown_without_header_or_false_value(self):
        for headers in ({}, {"X-Auth-Request-User": ""}, {"X-Auth-Request-User": "0"}):
            with self.subTest(headers=headers):
                self.assertIn(b"user unknown</p>", self.body("/?day=2026-10-15", headers=headers))

    def test_user_header_name_case_insensitive(self):
        body = self.body("/?day=2026-10-15", headers={"x-auth-request-user": "jdoe"})
        self.assertIn(b"user jdoe</p>", body)

    def test_only_the_ingress_header_names_the_user(self):
        for name in ("X-Forwarded-User", "Remote-User", "X-Remote-User", "X-Auth-Request-Email",
                     "X-Auth-Request-Preferred-Username"):
            with self.subTest(header=name):
                self.assertIn(b"user unknown</p>", self.body("/?day=2026-10-15", headers={name: "jdoe"}))
        body = self.body("/?day=2026-10-15", headers={"Authorization": "Basic amRvZTpzZWNyZXQ="})  # jdoe:secret
        self.assertIn(b"user unknown</p>", body)

    def test_user_escaped_and_bytes_kept(self):
        req = urllib.request.Request(self.srv.base + "/?day=2026-10-15")
        req.add_header("X-Auth-Request-User", "<a&\"b'>é".encode().decode("latin-1"))
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read()
        self.assertIn("user &lt;a&amp;&quot;b&#39;&gt;é</p>".encode(), body)

    def test_cells_escaped(self):
        body = self.body("/?day=2030-01-05")
        self.assertIn(b"<tr><td>&lt;b&gt;&amp;&quot;&#39;&lt;/b&gt;</td><td>&lt;i&gt;</td><td>&quot;x&quot;</td>"
                      b"<td>0.10000</td><td>n/a</td></tr>\n", body)

    def test_day_escaped_in_title_and_line(self):
        body = self.body("/?day=2026-10-15%0A")
        self.assertIn(b"<p>Business date 2026-10-15\n, user unknown</p>", body)


class PreviousCloseZero(ServerTestCase):
    rates = {"2030-01-01": HEADER + "EURUSD,1,1.1,1.0,0,1,3\n", "2030-01-02": HEADER + "EURUSD,1,1.1,1.0,1.05,1,3\n"}

    def test_500_with_log_line(self):
        status, headers, body = self.srv.get("/fx/fx-report.cgi?day=2030-01-02")
        self.assertEqual(status, 500)
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertNotIn(b"<table>", body)
        lines = self.srv.log.getvalue().splitlines()
        self.assertEqual(len(lines), 1)
        self.assertIn('"GET /fx/fx-report.cgi?day=2030-01-02 HTTP/1.1" 500', lines[0])
        self.assertIn('error="ZeroDivisionError: float division by zero"', lines[0])


class HealthAndRouting(ServerTestCase):
    def test_health(self):
        status, headers, body = self.srv.get("/health")
        self.assertEqual((status, body), (200, b"ok\n"))
        self.assertEqual(headers["Cache-Control"], "no-store")

    def test_health_503_when_rates_dir_unreadable(self):
        self.srv.httpd.rates_dir = str(self.dir / "missing")
        status, _, _ = self.srv.get("/health")
        self.assertEqual(status, 503)

    def test_unknown_path_404(self):
        for path in ("/fx/other.cgi", "/fx/", "/health/x"):
            with self.subTest(path=path):
                self.assertEqual(self.srv.get(path)[0], 404)

    def test_one_log_line_per_request(self):
        self.srv.get("/?day=2026-10-15", headers={"X-Auth-Request-User": "jdoe"})
        self.srv.get("/health")
        self.srv.get("/nope")
        self.srv.get("/", method="POST")
        lines = self.srv.log.getvalue().splitlines()
        self.assertEqual(len(lines), 4, lines)
        self.assertRegex(lines[0], r'^127\.0\.0\.1 - jdoe \[.*\] "GET /\?day=2026-10-15 HTTP/1\.1" 200 1096 ')
        self.assertIn('"GET /health HTTP/1.1" 200 3', lines[1])
        self.assertIn('"GET /nope HTTP/1.1" 404', lines[2])
        self.assertIn('"POST / HTTP/1.1" 501', lines[3])

    def test_log_escapes_control_characters(self):
        self.srv.get("/", headers={"X-Auth-Request-User": "a\x1b[31mb"})
        self.assertIn("a\\x1b[31mb", self.srv.log.getvalue())


class RunAsScript(unittest.TestCase):
    """`python server.py` with config from env, from a copy of app/ so a stray .pyc or file would show."""

    def test_env_config_and_nothing_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp) / "app"
            app.mkdir()
            for name in ("server.py", "rates.py"):
                shutil.copy(APP / name, app)
            cwd = Path(tmp) / "cwd"
            cwd.mkdir()
            with socket.socket() as s:
                s.bind(("127.0.0.1", 0))
                port = s.getsockname()[1]
            env = {k: v for k, v in os.environ.items() if k != "PYTHONDONTWRITEBYTECODE"}
            env.update(RATES_DIR=str(GOLDEN / "rates"), PORT=str(port), TZ="Pacific/Kiritimati")
            proc = subprocess.Popen([sys.executable, str(app / "server.py")], cwd=cwd, env=env,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                base = f"http://127.0.0.1:{port}"
                for _ in range(50):
                    try:
                        urllib.request.urlopen(base + "/health", timeout=1).close()
                        break
                    except OSError:
                        time.sleep(0.1)
                with urllib.request.urlopen(base + "/fx/fx-report.cgi?day=2026-10-16", timeout=5) as resp:
                    self.assertEqual(resp.read(), golden("day-2026-10-16"))
                with urllib.request.urlopen(base + "/", timeout=5) as resp:
                    expected = (datetime.now(ZoneInfo("Pacific/Kiritimati")) - timedelta(days=1)).strftime("%Y-%m-%d")
                    self.assertIn(f"Business date {expected},".encode(), resp.read())
            finally:
                proc.terminate()
                out, err = proc.communicate(timeout=10)
            self.assertEqual(proc.returncode, 0, err)
            self.assertEqual(sorted(p.name for p in app.iterdir()), ["rates.py", "server.py"])
            self.assertEqual(list(cwd.iterdir()), [])
            lines = out.splitlines()
            self.assertIn(f"RATES_DIR={GOLDEN / 'rates'}", lines[0])
            self.assertEqual(len(lines), 4, out)  # startup line + three requests


if __name__ == "__main__":
    unittest.main()
