"""fx-report over HTTP: the page cgi-bin/fx-report.cgi printed, served by the Python 3.12 standard library.

    RATES_DIR=../tests/golden/rates PORT=8080 python app/server.py

GET /fx/fx-report.cgi?day=<yyyy-mm-dd> (the old path, kept for the desk's bookmarks) and GET / serve the report;
GET /health answers 200 while RATES_DIR is readable. Config from env only: RATES_DIR (default /mnt/rates-out),
TZ (zone for "yesterday", like localtime in the CGI) and PORT (default 8080). The signed-in user comes from the
X-Auth-Request-User header the ingress sign-in sets. One log line per request on stdout; nothing is written to disk.
"""
import sys

sys.dont_write_bytecode = True  # importing rates must not write app/__pycache__ (read-only root filesystem)

import os  # noqa: E402
import re  # noqa: E402
import signal  # noqa: E402
import threading  # noqa: E402
import time  # noqa: E402
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer  # noqa: E402
from urllib.parse import unquote  # noqa: E402

import rates  # noqa: E402

DEFAULT_RATES_DIR = "/mnt/rates-out"
DEFAULT_PORT = 8080
REPORT_PATHS = ("/fx/fx-report.cgi", "/")
USER_HEADER = "X-Auth-Request-User"
PAGE_TYPE = "text/html; charset=utf-8"
PAGE_CACHE = "max-age=3600"  # was mod_expires "access plus 1 hour"
EMPTY_DAY = "No rates file for this day yet."

# The CGI's /^\d{4}-\d\d-\d\d$/ on bytes: ASCII digits, and Perl's $ also matches before a final newline.
_DAY = re.compile(r"\d{4}-\d\d-\d\d\n?", re.ASCII)
_PARAM_SEP = re.compile(r"[&;]")
_PERCENT = re.compile(rb"%(?:([0-9a-fA-F]{2})|u([0-9a-fA-F]{4}))")
_ESCAPES = {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}
_ESCAPE = re.compile("[&<>\"']")
_CONTROL = {c: f"\\x{c:02x}" for c in (*range(0x20), 0x7f)}

_HEAD = ('<!DOCTYPE html\n\tPUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"\n'
         '\t "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">\n'
         '<html xmlns="http://www.w3.org/1999/xhtml" lang="en-US" xml:lang="en-US">\n<head>\n'
         '<title>{title}</title>\n<style type="text/css">\n<!--/* <![CDATA[ */\n'
         'body{{font-family:Arial;margin:2em}}td{{padding:3px 10px}}\n\n/* ]]> */-->\n</style>\n'
         '<meta http-equiv="Content-Type" content="text/html; charset=utf-8" />\n</head>\n<body>\n')
_TABLE_HEAD = "<table><tr><th>Pair</th><th>Close</th><th>Average mid</th><th>Range</th><th>Change</th></tr>"
_FOOT = "\n</body>\n</html>"


def escape_html(text):
    """CGI.pm escapeHTML (HTML::Entities on &<>"'); other bytes pass through."""
    return _ESCAPE.sub(lambda m: _ESCAPES[m.group()], text)


def _percent_byte(m):
    return bytes([int(m[1], 16)]) if m[1] else chr(int(m[2], 16)).encode("utf-8", "surrogatepass")


def _unescape(text):
    """CGI::Util::unescape: + is a space, %XX a byte, %uXXXX a character in UTF-8. Values stay bytes, as in Perl
    (decoded with surrogateescape so they round-trip)."""
    raw = text.replace("+", " ").encode("utf-8", "surrogateescape")
    raw = _PERCENT.sub(_percent_byte, raw)
    return raw.decode("utf-8", "surrogateescape")


def query_param(query, name):
    """First value of a parameter as CGI.pm's param() returns it (pairs split on & and ;), None when absent."""
    for pair in _PARAM_SEP.split(query):
        key, _, value = pair.partition("=")
        if _unescape(key) == name:
            return _unescape(value)
    return None


def report_day(value, now=None):
    """The CGI's day: a missing or false value ('' or '0', Perl truth) is yesterday in TZ (localtime of now - 1
    day, as the CGI did), and anything not shaped like yyyy-mm-dd becomes ''."""
    if not value or value == "0":
        value = time.strftime("%Y-%m-%d", time.localtime(int(time.time() if now is None else now) - 86400))
    return value if _DAY.fullmatch(value) else ""


def _days_from_civil(y, m, d):
    y -= m <= 2
    era = y // 400
    yoe = y - era * 400
    doy = (153 * (m + (-3 if m > 2 else 9)) + 2) // 5 + d - 1
    return era * 146097 + yoe * 365 + yoe // 4 - yoe // 100 + doy - 719468


def _civil_from_days(z):
    z += 719468
    era = z // 146097
    doe = z - era * 146097
    yoe = (doe - doe // 1460 + doe // 36524 - doe // 146096) // 365
    doy = doe - (365 * yoe + yoe // 4 - yoe // 100)
    mp = (5 * doy + 2) // 153
    d = doy - (153 * mp + 2) // 5 + 1
    m = mp + (3 if mp < 10 else -9)
    return yoe + era * 400 + (m <= 2), m, d


def previous_day(day):
    """The CGI's strftime('%Y-%m-%d', 0, 0, 12, $d - 1, $m - 1, $y - 1900): the calendar day before, with
    out-of-range months and days carried over (2026-13-05 -> 2027-01-04) and glibc's unpadded %Y."""
    parts = day.split("-")
    y, m, d = (int(rates.perl_num(p)) for p in (parts + [None] * 3)[:3])
    y, m = y + (m - 1) // 12, (m - 1) % 12 + 1
    y, m, d = _civil_from_days(_days_from_civil(y, m, 1) + d - 2)
    return f"{y}-{m:02d}-{d:02d}"


def render_report(day, user, rates_dir):
    """The page fx-report.cgi printed for a validated day, as bytes; a false user ('' or '0', Perl truth) is
    'unknown'. Raises ZeroDivisionError when a pair's
    previous close is 0, like FxReport::Rates::moves."""
    today = rates.read_day(f"{rates_dir}/rates-{day}.csv")
    prev = rates.read_day(f"{rates_dir}/rates-{previous_day(day)}.csv")
    out = [_HEAD.format(title=escape_html(f"FX desk report {day}")), "<h1>FX desk report</h1>",
           f"<p>Business date {escape_html(day)}, user {escape_html(user if user and user != '0' else 'unknown')}</p>"]
    if today is None:
        out.append(f"<p>{EMPTY_DAY}</p>")
    else:
        rows = rates.moves(today, prev)
        out.append(_TABLE_HEAD)
        for r in rows:
            cells = (r["pair"], r["close"] or "", r["avg"] or "", rates.format_range(r["range"]),
                     rates.format_change(r["chg_pct"]))
            out.append("<tr>" + "".join(f"<td>{escape_html(c)}</td>" for c in cells) + "</tr>\n")
        out.append("</table>")
    out.append(_FOOT)
    return "".join(out).encode("utf-8", "surrogateescape")


def rates_dir_readable(rates_dir):
    try:
        with os.scandir(rates_dir):
            pass
    except OSError:
        return False
    return os.access(rates_dir, os.X_OK)


class ReportServer(ThreadingHTTPServer):
    def __init__(self, address, rates_dir=DEFAULT_RATES_DIR, log=None):
        super().__init__(address, ReportHandler)
        self.rates_dir = rates_dir
        self.log = log or sys.stdout
        self._log_lock = threading.Lock()

    def log_line(self, line):
        with self._log_lock:
            print(line.translate(_CONTROL), file=self.log, flush=True)


class ReportHandler(BaseHTTPRequestHandler):
    server_version = "fx-report"
    sys_version = ""
    protocol_version = "HTTP/1.1"

    def version_string(self):
        return self.server_version

    def do_GET(self):
        self._handle(send_body=True)

    def do_HEAD(self):
        self._handle(send_body=False)

    def _user(self):
        """The signed-in user as Perl saw REMOTE_USER: the header's bytes, '' when missing."""
        value = self.headers.get(USER_HEADER, "")
        return value.encode("latin-1", "surrogateescape").decode("utf-8", "surrogateescape")

    def _handle(self, send_body):
        started = time.monotonic()
        path, _, query = self.path.partition("?")
        path = unquote(path)
        error = None
        if path in REPORT_PATHS:
            user = self._user()
            try:
                body = render_report(report_day(query_param(query, "day")), user, self.server.rates_dir)
                status, ctype, cache = 200, PAGE_TYPE, PAGE_CACHE
            except Exception as exc:  # the CGI died here (Illegal division by zero for a previous close of 0)
                error = f"{type(exc).__name__}: {exc}"
                status, ctype, cache, body = 500, "text/plain; charset=utf-8", "no-store", b"Internal Server Error\n"
        elif path == "/health":
            user = ""
            ok = rates_dir_readable(self.server.rates_dir)
            status, ctype, cache = (200 if ok else 503), "text/plain; charset=utf-8", "no-store"
            body = b"ok\n" if ok else b"rates directory not readable\n"
        else:
            user = ""
            status, ctype, cache, body = 404, "text/plain; charset=utf-8", "no-store", b"Not Found\n"

        self.send_response_only(status)
        self.send_header("Server", self.version_string())
        self.send_header("Date", self.date_time_string())
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", cache)
        self.end_headers()
        if send_body:
            self.wfile.write(body)
        self._access_log(status, len(body) if send_body else 0, user, started, error)

    def _access_log(self, status, size, user, started, error=None):
        ms = (time.monotonic() - started) * 1000
        line = (f'{self.address_string()} - {user or "-"} [{self.log_date_time_string()}] "{self.requestline}" '
                f"{status} {size} {ms:.1f}ms")
        if error:
            line += f' error="{error}"'
        self.server.log_line(line)

    def log_request(self, code="-", size="-"):  # requests http.server answers itself (400, 501, ...)
        self.server.log_line(f'{self.address_string()} - - [{self.log_date_time_string()}] "{self.requestline}" '
                             f"{getattr(code, 'value', code)} {size}")

    def log_error(self, format, *args):  # noqa: A002 (BaseHTTPRequestHandler signature); log_request has the line
        pass


def main():
    rates_dir = os.environ.get("RATES_DIR") or DEFAULT_RATES_DIR
    port = int(os.environ.get("PORT") or DEFAULT_PORT)
    time.tzset()
    server = ReportServer(("", port), rates_dir)
    signal.signal(signal.SIGTERM, lambda *_: threading.Thread(target=server.shutdown).start())
    server.log_line(f"fx-report listening on :{server.server_address[1]}, RATES_DIR={rates_dir}, "
                    f"TZ={os.environ.get('TZ', '')}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
