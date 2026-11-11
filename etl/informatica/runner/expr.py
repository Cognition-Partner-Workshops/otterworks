"""PowerCenter transformation-language expressions.

Expressions are parsed once and compiled into Python closures that take a
port-value dict.  Null handling follows the Integration Service defaults:

* arithmetic and comparison with a NULL operand yield NULL;
* AND / OR / NOT use three-valued logic;
* a condition that evaluates to NULL is treated as FALSE by IIF, Filter,
  Router and DECODE(TRUE, ...);
* ``||`` treats a NULL operand as an empty string, and returns NULL only
  when both operands are NULL;
* IIF without a false value returns 0 for a numeric true value, an empty
  string for a string true value and NULL for a date.
"""

from __future__ import annotations

import calendar
import datetime as dt
import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

DD_INSERT, DD_UPDATE, DD_DELETE, DD_REJECT = 0, 1, 2, 3

BUILTIN_CONSTANTS = {
    "DD_INSERT": DD_INSERT,
    "DD_UPDATE": DD_UPDATE,
    "DD_DELETE": DD_DELETE,
    "DD_REJECT": DD_REJECT,
    "TRUE": 1,
    "FALSE": 0,
}

DEFAULT_DATE_FORMAT = "MM/DD/YYYY HH24:MI:SS.US"


class ExpressionError(Exception):
    """Parse or compile error in an expression."""


class TransformationError(Exception):
    """Row-level error raised while evaluating an expression (row is rejected)."""


class AbortSession(Exception):
    """Raised by ABORT()."""


# --------------------------------------------------------------------------- lexer

_TOKEN_RE = re.compile(
    r"""
    (?P<ws>\s+)
  | (?P<comment>(--|//)[^\n]*)
  | (?P<number>\d+\.\d*|\.\d+|\d+)
  | (?P<string>'(?:[^']|'')*')
  | (?P<lkp>:LKP\.[A-Za-z_][A-Za-z0-9_]*)
  | (?P<ident>\$\$?[A-Za-z_][A-Za-z0-9_.]*|[A-Za-z_@#][A-Za-z0-9_$#@]*)
  | (?P<op>\|\||<=|>=|<>|!=|\^=|[-+*/%<>=(),])
    """,
    re.VERBOSE | re.IGNORECASE,
)

KEYWORDS = {"AND", "OR", "NOT", "NULL"}


def tokenize(text: str):
    pos = 0
    out = []
    while pos < len(text):
        m = _TOKEN_RE.match(text, pos)
        if not m:
            raise ExpressionError(f"unexpected character {text[pos]!r} at {pos} in: {text}")
        pos = m.end()
        kind = m.lastgroup
        val = m.group(kind)
        if kind in ("ws", "comment"):
            continue
        if kind == "ident" and val.upper() in KEYWORDS:
            out.append(("kw", val.upper()))
        elif kind == "string":
            out.append(("string", val[1:-1].replace("''", "'")))
        elif kind == "number":
            out.append(("number", val))
        elif kind == "lkp":
            out.append(("lkp", val[5:]))
        else:
            out.append((kind, val))
    out.append(("eof", None))
    return out


# --------------------------------------------------------------------------- AST


class Node:
    kind = "node"


class Lit(Node):
    def __init__(self, value):
        self.value = value


class Ref(Node):
    def __init__(self, name):
        self.name = name


class Unary(Node):
    def __init__(self, op, operand):
        self.op, self.operand = op, operand


class Binary(Node):
    def __init__(self, op, left, right):
        self.op, self.left, self.right = op, left, right


class Call(Node):
    def __init__(self, name, args):
        self.name, self.args = name.upper(), args


class LkpCall(Node):
    def __init__(self, name, args):
        self.name, self.args = name, args


class Parser:
    # precedence: OR < AND < NOT < (= <> != ^=) < (< <= > >=) < || < (+ -) < (* / %) < unary
    def __init__(self, text):
        self.text = text
        self.toks = tokenize(text)
        self.i = 0

    def peek(self):
        return self.toks[self.i]

    def take(self):
        t = self.toks[self.i]
        self.i += 1
        return t

    def expect(self, kind, val=None):
        t = self.take()
        if t[0] != kind or (val is not None and t[1] != val):
            raise ExpressionError(f"expected {val or kind}, got {t[1]!r} in: {self.text}")
        return t

    def parse(self):
        node = self.p_or()
        if self.peek()[0] != "eof":
            raise ExpressionError(f"unexpected {self.peek()[1]!r} in: {self.text}")
        return node

    def p_or(self):
        node = self.p_and()
        while self.peek() == ("kw", "OR"):
            self.take()
            node = Binary("OR", node, self.p_and())
        return node

    def p_and(self):
        node = self.p_not()
        while self.peek() == ("kw", "AND"):
            self.take()
            node = Binary("AND", node, self.p_not())
        return node

    def p_not(self):
        if self.peek() == ("kw", "NOT"):
            self.take()
            return Unary("NOT", self.p_not())
        return self.p_eq()

    def p_eq(self):
        node = self.p_rel()
        while self.peek()[0] == "op" and self.peek()[1] in ("=", "<>", "!=", "^="):
            op = self.take()[1]
            node = Binary("<>" if op in ("!=", "^=") else op, node, self.p_rel())
        return node

    def p_rel(self):
        node = self.p_concat()
        while self.peek()[0] == "op" and self.peek()[1] in ("<", "<=", ">", ">="):
            op = self.take()[1]
            node = Binary(op, node, self.p_concat())
        return node

    def p_concat(self):
        node = self.p_add()
        while self.peek() == ("op", "||"):
            self.take()
            node = Binary("||", node, self.p_add())
        return node

    def p_add(self):
        node = self.p_mul()
        while self.peek()[0] == "op" and self.peek()[1] in ("+", "-"):
            op = self.take()[1]
            node = Binary(op, node, self.p_mul())
        return node

    def p_mul(self):
        node = self.p_unary()
        while self.peek()[0] == "op" and self.peek()[1] in ("*", "/", "%"):
            op = self.take()[1]
            node = Binary(op, node, self.p_unary())
        return node

    def p_unary(self):
        t = self.peek()
        if t[0] == "op" and t[1] in ("+", "-"):
            self.take()
            return Unary(t[1], self.p_unary())
        return self.p_atom()

    def p_atom(self):
        t = self.take()
        kind, val = t
        if kind == "number":
            return Lit(Decimal(val) if "." in val else int(val))
        if kind == "string":
            return Lit(val)
        if kind == "kw" and val == "NULL":
            return Lit(None)
        if kind == "op" and val == "(":
            node = self.p_or()
            self.expect("op", ")")
            return node
        if kind == "lkp":
            return LkpCall(val, self._args())
        if kind == "ident":
            if self.peek() == ("op", "("):
                return Call(val, self._args())
            return Ref(val)
        raise ExpressionError(f"unexpected {val!r} in: {self.text}")

    def _args(self):
        self.expect("op", "(")
        args = []
        if self.peek() == ("op", ")"):
            self.take()
            return args
        while True:
            if self.peek() == ("op", "*"):
                self.take()
                args.append(Lit("*"))
            else:
                args.append(self.p_or())
            t = self.take()
            if t == ("op", ")"):
                return args
            if t != ("op", ","):
                raise ExpressionError(f"expected , or ) in: {self.text}")


def parse(text: str) -> Node:
    return Parser(text).parse()


# --------------------------------------------------------------------------- helpers


def truthy(v) -> bool:
    """Condition semantics: NULL and zero are FALSE."""
    if v is None:
        return False
    if isinstance(v, str):
        try:
            return Decimal(v.strip() or "0") != 0
        except InvalidOperation:
            return False
    return v != 0


def _num(v):
    if v is None or isinstance(v, (int, Decimal)):
        return v
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, float):
        return Decimal(repr(v))
    if isinstance(v, str):
        try:
            s = v.strip()
            return int(s) if re.fullmatch(r"[-+]?\d+", s) else Decimal(s)
        except InvalidOperation as e:
            raise TransformationError(f"invalid number: {v!r}") from e
    raise TransformationError(f"not a number: {v!r}")


def _cmp_norm(a, b):
    if isinstance(a, (int, Decimal, float)) and isinstance(b, (int, Decimal, float)):
        return _num(a), _num(b)
    if isinstance(a, dt.datetime) and isinstance(b, dt.datetime):
        return a, b
    if isinstance(a, str) and isinstance(b, str):
        return a, b
    if isinstance(a, (int, Decimal)) and isinstance(b, str):
        return a, _num(b)
    if isinstance(a, str) and isinstance(b, (int, Decimal)):
        return _num(a), b
    raise TransformationError(f"cannot compare {type(a).__name__} with {type(b).__name__}")


def _to_str(v):
    if v is None:
        return None
    if isinstance(v, str):
        return v
    if isinstance(v, dt.datetime):
        return format_date(v, DEFAULT_DATE_FORMAT)
    if isinstance(v, Decimal):
        return format(v, "f")
    return str(v)


# ------------------------------------------------------------------ date formats

_DATE_TOKENS = [
    "HH24", "HH12", "YYYY", "MONTH", "A.M.", "P.M.", "DDD", "DAY", "YYY", "MON", "HH",
    "MI", "SS", "MS", "US", "NS", "MM", "DD", "DY", "YY", "RR", "AM", "PM", "Y", "J",
]
_MONTHS = [m.upper() for m in calendar.month_name[1:]]
_MON = [m.upper() for m in calendar.month_abbr[1:]]
_DAYS = [d.upper() for d in calendar.day_name]
_DY = [d.upper() for d in calendar.day_abbr]


def _split_format(fmt: str):
    parts, i = [], 0
    while i < len(fmt):
        up = fmt[i:].upper()
        for tok in _DATE_TOKENS:
            if up.startswith(tok):
                parts.append(("tok", tok))
                i += len(tok)
                break
        else:
            if fmt[i] == '"':
                j = fmt.index('"', i + 1)
                parts.append(("lit", fmt[i + 1 : j]))
                i = j + 1
            else:
                parts.append(("lit", fmt[i]))
                i += 1
    return parts


_FMT_CACHE: dict = {}

_TOKEN_PATTERNS = {
    "YYYY": r"(?P<Y>\d{4})", "YYY": r"(?P<Y3>\d{3})", "YY": r"(?P<Y2>\d{2})", "RR": r"(?P<R2>\d{2})",
    "Y": r"(?P<Y1>\d)", "MM": r"(?P<M>\d{1,2})", "MON": r"(?P<MON>[A-Za-z]{3})",
    "MONTH": r"(?P<MONTH>[A-Za-z]+)", "DD": r"(?P<D>\d{1,2})", "DDD": r"(?P<DDD>\d{1,3})",
    "DY": r"[A-Za-z]{3}", "DAY": r"[A-Za-z]+", "HH24": r"(?P<H24>\d{1,2})",
    "HH12": r"(?P<H12>\d{1,2})", "HH": r"(?P<H12>\d{1,2})", "MI": r"(?P<MI>\d{1,2})",
    "SS": r"(?P<S>\d{1,2})", "MS": r"(?P<MS>\d{1,3})", "US": r"(?P<US>\d{1,6})",
    "NS": r"(?P<NS>\d{1,9})", "AM": r"(?P<AP>[AaPp][Mm])", "PM": r"(?P<AP>[AaPp][Mm])",
    "A.M.": r"(?P<AP2>[AaPp]\.[Mm]\.)", "P.M.": r"(?P<AP2>[AaPp]\.[Mm]\.)", "J": r"(?P<J>\d{1,7})",
}


def _compile_date_format(fmt: str):
    if fmt in _FMT_CACHE:
        return _FMT_CACHE[fmt]
    rx = ""
    seen = set()
    for kind, val in _split_format(fmt):
        if kind == "lit":
            rx += re.escape(val)
        else:
            pat = _TOKEN_PATTERNS[val]
            m = re.match(r"\(\?P<(\w+)>", pat)
            if m and m.group(1) in seen:
                pat = re.sub(r"\(\?P<\w+>", "(?:", pat, count=1)
            elif m:
                seen.add(m.group(1))
            rx += pat
    compiled = re.compile(rx + r"\Z")
    _FMT_CACHE[fmt] = compiled
    return compiled


def parse_date(s: str, fmt: str = DEFAULT_DATE_FORMAT) -> dt.datetime:
    m = _compile_date_format(fmt).match(s)
    if not m:
        raise TransformationError(f"Invalid date: [{s}] does not match format [{fmt}]")
    g = {k: v for k, v in m.groupdict().items() if v is not None}
    try:
        if "J" in g:
            base = dt.datetime(1, 1, 1) + dt.timedelta(days=int(g["J"]) - 1721426)
            return base
        if "Y" in g:
            year = int(g["Y"])
        elif "Y3" in g:
            year = 2000 + int(g["Y3"]) % 1000 if int(g["Y3"]) < 1000 else int(g["Y3"])
        elif "Y2" in g:
            year = 2000 + int(g["Y2"])
        elif "R2" in g:
            yy = int(g["R2"])
            year = 2000 + yy if yy < 50 else 1900 + yy
        elif "Y1" in g:
            year = 2000 + int(g["Y1"])
        else:
            year = dt.date.today().year
        if "M" in g:
            month = int(g["M"])
        elif "MON" in g:
            month = _MON.index(g["MON"].upper()) + 1
        elif "MONTH" in g:
            month = _MONTHS.index(g["MONTH"].upper()) + 1
        else:
            month = 1
        day = int(g.get("D", 1))
        if "DDD" in g:
            d0 = dt.datetime(year, 1, 1) + dt.timedelta(days=int(g["DDD"]) - 1)
            month, day = d0.month, d0.day
        if "H24" in g:
            hour = int(g["H24"])
        elif "H12" in g:
            hour = int(g["H12"]) % 12
            ap = (g.get("AP") or g.get("AP2") or "AM").upper()
            if ap.startswith("P"):
                hour += 12
        else:
            hour = 0
        micro = 0
        if "MS" in g:
            micro = int(g["MS"].ljust(3, "0")) * 1000
        if "US" in g:
            micro = int(g["US"].ljust(6, "0"))
        if "NS" in g:
            micro = int(g["NS"].ljust(9, "0")) // 1000
        return dt.datetime(year, month, day, hour, int(g.get("MI", 0)), int(g.get("S", 0)), micro)
    except (ValueError, IndexError) as e:
        raise TransformationError(f"Invalid date: [{s}] for format [{fmt}]: {e}") from e


def format_date(d: dt.datetime, fmt: str = DEFAULT_DATE_FORMAT) -> str:
    out = []
    for kind, val in _split_format(fmt):
        if kind == "lit":
            out.append(val)
            continue
        out.append({
            "YYYY": f"{d.year:04d}", "YYY": f"{d.year % 1000:03d}", "YY": f"{d.year % 100:02d}",
            "RR": f"{d.year % 100:02d}", "Y": f"{d.year % 10}", "MM": f"{d.month:02d}",
            "MON": _MON[d.month - 1], "MONTH": _MONTHS[d.month - 1], "DD": f"{d.day:02d}",
            "DDD": f"{d.timetuple().tm_yday:03d}", "DY": _DY[d.weekday()], "DAY": _DAYS[d.weekday()],
            "HH24": f"{d.hour:02d}", "HH12": f"{(d.hour % 12) or 12:02d}", "HH": f"{(d.hour % 12) or 12:02d}",
            "MI": f"{d.minute:02d}", "SS": f"{d.second:02d}", "MS": f"{d.microsecond // 1000:03d}",
            "US": f"{d.microsecond:06d}", "NS": f"{d.microsecond * 1000:09d}",
            "AM": "AM" if d.hour < 12 else "PM", "PM": "AM" if d.hour < 12 else "PM",
            "A.M.": "A.M." if d.hour < 12 else "P.M.", "P.M.": "A.M." if d.hour < 12 else "P.M.",
            "J": str(d.toordinal() + 1721425),
        }[val])
    return "".join(out)


def _date_unit(fmt: str) -> str:
    f = (fmt or "").upper().strip()
    if f in ("Y", "YY", "YYY", "YYYY"):
        return "year"
    if f in ("MM", "MON", "MONTH"):
        return "month"
    if f in ("D", "DD", "DDD", "DY", "DAY"):
        return "day"
    if f in ("HH", "HH12", "HH24"):
        return "hour"
    if f == "MI":
        return "minute"
    if f == "SS":
        return "second"
    if f == "MS":
        return "ms"
    if f == "US":
        return "us"
    if f == "NS":
        return "ns"
    raise TransformationError(f"invalid date format string: {fmt!r}")


def add_to_date(d, fmt, amount):
    if d is None or amount is None:
        return None
    if not isinstance(d, dt.datetime):
        raise TransformationError(f"ADD_TO_DATE expects a date, got {d!r}")
    unit = _date_unit(fmt)
    n = _num(amount)
    if unit in ("year", "month"):
        months = int(n) * (12 if unit == "year" else 1)
        total = d.year * 12 + (d.month - 1) + months
        y, m = divmod(total, 12)
        m += 1
        last = calendar.monthrange(y, m)[1]
        return d.replace(year=y, month=m, day=min(d.day, last))
    delta = {
        "day": dt.timedelta(days=float(n)),
        "hour": dt.timedelta(hours=float(n)),
        "minute": dt.timedelta(minutes=float(n)),
        "second": dt.timedelta(seconds=float(n)),
        "ms": dt.timedelta(milliseconds=float(n)),
        "us": dt.timedelta(microseconds=float(n)),
        "ns": dt.timedelta(microseconds=float(n) / 1000),
    }[unit]
    return d + delta


def date_diff(d1, d2, fmt):
    if d1 is None or d2 is None:
        return None
    unit = _date_unit(fmt)
    if unit in ("year", "month"):
        months = (d1.year - d2.year) * 12 + (d1.month - d2.month)
        months = Decimal(months) + Decimal((d1.day - d2.day)) / 31
        return months / 12 if unit == "year" else months
    secs = Decimal(str((d1 - d2).total_seconds()))
    div = {"day": 86400, "hour": 3600, "minute": 60, "second": 1, "ms": Decimal("0.001"),
           "us": Decimal("0.000001"), "ns": Decimal("0.000000001")}[unit]
    return secs / div


def trunc_date(d, fmt="DD"):
    if d is None:
        return None
    unit = _date_unit(fmt)
    if unit == "year":
        return d.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    if unit == "month":
        return d.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if unit == "day":
        return d.replace(hour=0, minute=0, second=0, microsecond=0)
    if unit == "hour":
        return d.replace(minute=0, second=0, microsecond=0)
    if unit == "minute":
        return d.replace(second=0, microsecond=0)
    return d.replace(microsecond=0)


def get_date_part(d, fmt):
    if d is None:
        return None
    unit = _date_unit(fmt)
    return {"year": d.year, "month": d.month, "day": d.day, "hour": d.hour,
            "minute": d.minute, "second": d.second, "ms": d.microsecond // 1000,
            "us": d.microsecond, "ns": d.microsecond * 1000}[unit]


# ------------------------------------------------------------------ functions


def _trim(s, chars, left):
    if s is None:
        return None
    s = _to_str(s)
    if chars is None:
        chars = " "
    return s.lstrip(chars) if left else s.rstrip(chars)


def _round(v, places=0):
    if v is None:
        return None
    if isinstance(v, dt.datetime):
        return trunc_date(v, places if isinstance(places, str) else "DD")
    v = _num(v)
    p = int(places or 0)
    q = Decimal(1).scaleb(-p)
    r = Decimal(v).quantize(q, rounding=ROUND_HALF_UP)
    return int(r) if p <= 0 and isinstance(v, int) else r


def _trunc(v, places=0):
    if v is None:
        return None
    if isinstance(v, dt.datetime):
        return trunc_date(v, places if isinstance(places, str) else "DD")
    v = Decimal(_num(v))
    p = int(places or 0)
    q = Decimal(1).scaleb(-p)
    return v.quantize(q, rounding="ROUND_DOWN")


def _substr(s, start, length=None):
    if s is None or start is None:
        return None
    s = _to_str(s)
    start = int(start)
    if start == 0:
        start = 1
    idx = start - 1 if start > 0 else len(s) + start
    if idx < 0:
        idx = 0
    if length is None:
        return s[idx:]
    length = int(length)
    if length <= 0:
        return ""
    return s[idx : idx + length]


def _instr(s, search, start=1, occurrence=1):
    if s is None or search is None:
        return None
    s, search = _to_str(s), _to_str(search)
    pos = int(start) - 1
    for _ in range(int(occurrence)):
        idx = s.find(search, pos)
        if idx < 0:
            return 0
        pos = idx + 1
    return pos


def _to_integer(v, flag=None):
    if v is None:
        return None
    if isinstance(v, str):
        s = v.strip()
        m = re.match(r"[-+]?\d+(\.\d*)?", s)
        if not m:
            raise TransformationError(f"TO_INTEGER: invalid number [{v}]")
        v = Decimal(m.group(0))
    v = Decimal(_num(v))
    if flag is not None and not truthy(flag):
        return int(v.quantize(Decimal(1), rounding=ROUND_HALF_UP))
    return int(v)


def _to_decimal(v, scale=None):
    if v is None:
        return None
    if isinstance(v, str):
        m = re.match(r"\s*[-+]?(\d+(\.\d*)?|\.\d+)", v)
        if not m:
            raise TransformationError(f"TO_DECIMAL: invalid number [{v}]")
        v = Decimal(m.group(0).strip())
    v = Decimal(_num(v))
    if scale is not None:
        v = v.quantize(Decimal(1).scaleb(-int(scale)), rounding=ROUND_HALF_UP)
    return v


def _to_char(v, fmt=None):
    if v is None:
        return None
    if isinstance(v, dt.datetime):
        return format_date(v, fmt or DEFAULT_DATE_FORMAT)
    return _to_str(v)


def _to_date(v, fmt=None):
    if v is None:
        return None
    if isinstance(v, dt.datetime):
        return v
    return parse_date(_to_str(v), fmt or DEFAULT_DATE_FORMAT)


def _is_date(v, fmt=None):
    if v is None:
        return None
    try:
        _to_date(v, fmt)
        return 1
    except TransformationError:
        return 0


def _is_number(v):
    if v is None:
        return None
    return 1 if re.fullmatch(r"\s*[-+]?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?\s*", _to_str(v)) else 0


def _is_spaces(v):
    if v is None:
        return None
    return 1 if _to_str(v).strip(" ") == "" and len(_to_str(v)) > 0 else 0


def _pad(s, length, pad, left):
    if s is None or length is None:
        return None
    s = _to_str(s)
    n = int(length)
    pad = " " if pad is None else _to_str(pad)
    if len(s) >= n:
        return s[:n]
    fill = (pad * n)[: n - len(s)]
    return fill + s if left else s + fill


def _concat(a, b):
    if a is None and b is None:
        return None
    return (_to_str(a) or "") + (_to_str(b) or "")


def _replacestr(case_flag, s, *args):
    if s is None:
        return None
    if len(args) < 2:
        raise TransformationError("REPLACESTR needs old and new strings")
    *olds, new = args
    new = _to_str(new) or ""
    s = _to_str(s)
    for old in olds:
        if old is None or old == "":
            continue
        if truthy(case_flag):
            s = s.replace(_to_str(old), new)
        else:
            s = re.sub(re.escape(_to_str(old)), lambda _m: new, s, flags=re.IGNORECASE)
    return s


def _error(msg):
    raise TransformationError(_to_str(msg) or "ERROR()")


def _abort(msg):
    raise AbortSession(_to_str(msg) or "ABORT()")


SIMPLE_FUNCS = {
    "ISNULL": lambda v: 1 if v is None else 0,
    "NVL": lambda v, d: d if v is None else v,
    "LTRIM": lambda s, chars=None: _trim(s, chars, True),
    "RTRIM": lambda s, chars=None: _trim(s, chars, False),
    "UPPER": lambda s: None if s is None else _to_str(s).upper(),
    "LOWER": lambda s: None if s is None else _to_str(s).lower(),
    "INITCAP": lambda s: None if s is None else _to_str(s).title(),
    "LENGTH": lambda s: None if s is None else len(_to_str(s)),
    "SUBSTR": _substr,
    "INSTR": _instr,
    "CONCAT": _concat,
    "LPAD": lambda s, n, p=None: _pad(s, n, p, True),
    "RPAD": lambda s, n, p=None: _pad(s, n, p, False),
    "CHR": lambda n: None if n is None else chr(int(n)),
    "ASCII": lambda s: None if not s else ord(_to_str(s)[0]),
    "REPLACESTR": _replacestr,
    "TO_DATE": _to_date,
    "TO_CHAR": _to_char,
    "TO_INTEGER": _to_integer,
    "TO_BIGINT": _to_integer,
    "TO_DECIMAL": _to_decimal,
    "TO_FLOAT": lambda v: None if v is None else float(_num(_to_decimal(v))),
    "IS_DATE": _is_date,
    "IS_NUMBER": _is_number,
    "IS_SPACES": _is_spaces,
    "ADD_TO_DATE": add_to_date,
    "DATE_DIFF": date_diff,
    "GET_DATE_PART": get_date_part,
    "LAST_DAY": lambda d: None if d is None else d.replace(day=calendar.monthrange(d.year, d.month)[1]),
    "ROUND": _round,
    "TRUNC": _trunc,
    "ABS": lambda v: None if v is None else abs(_num(v)),
    "CEIL": lambda v: None if v is None else int(Decimal(_num(v)).to_integral_value(rounding="ROUND_CEILING")),
    "FLOOR": lambda v: None if v is None else int(Decimal(_num(v)).to_integral_value(rounding="ROUND_FLOOR")),
    "MOD": lambda a, b: None if a is None or b is None else _mod(a, b),
    "POWER": lambda a, b: None if a is None or b is None else Decimal(_num(a)) ** int(_num(b)),
    "SIGN": lambda v: None if v is None else (0 if _num(v) == 0 else (1 if _num(v) > 0 else -1)),
    "ERROR": _error,
    "ABORT": _abort,
}

AGGREGATE_FUNCS = {"SUM", "COUNT", "MAX", "MIN", "AVG", "FIRST", "LAST", "MEDIAN"}


def _mod(a, b):
    a, b = _num(a), _num(b)
    if b == 0:
        raise TransformationError("division by zero")
    r = abs(a) % abs(b)
    return -r if a < 0 else r


# ------------------------------------------------------------------ compiler


class CompileContext:
    """Static information the compiler needs.

    ``port_types`` maps port names (upper-case) to PowerCenter datatypes.
    ``params`` maps ``$$NAME`` to resolved string values.
    ``lookups`` maps unconnected Lookup names to callables.
    ``aggregate`` enables aggregate functions (Aggregator output ports).
    """

    def __init__(self, port_types=None, params=None, lookups=None, builtins=None, aggregate=False):
        self.port_types = {k.upper(): v for k, v in (port_types or {}).items()}
        self.params = {k.upper(): v for k, v in (params or {}).items()}
        self.lookups = {k.upper(): v for k, v in (lookups or {}).items()}
        self.builtins = {k.upper(): v for k, v in (builtins or {}).items()}
        self.aggregate = aggregate


def _static_type(node, cctx):
    if isinstance(node, Lit):
        if isinstance(node.value, str):
            return "string"
        if isinstance(node.value, (int, Decimal)):
            return "number"
        return None
    if isinstance(node, Ref):
        t = cctx.port_types.get(node.name.upper(), "")
        if "date" in t:
            return "date"
        if "string" in t or "char" in t or "text" in t:
            return "string"
        if t:
            return "number"
        return None
    if isinstance(node, Binary):
        if node.op == "||":
            return "string"
        if node.op in ("+", "-", "*", "/", "%"):
            lt = _static_type(node.left, cctx)
            return "date" if lt == "date" else "number"
        return "number"
    if isinstance(node, Call):
        n = node.name
        if n in ("TO_DATE", "ADD_TO_DATE", "LAST_DAY", "SYSDATE", "SESSSTARTTIME"):
            return "date"
        if n in ("LTRIM", "RTRIM", "UPPER", "LOWER", "SUBSTR", "TO_CHAR", "CONCAT", "LPAD",
                 "RPAD", "INITCAP", "REPLACESTR", "CHR"):
            return "string"
        if n in ("IIF",) and len(node.args) >= 2:
            return _static_type(node.args[1], cctx)
        if n == "DECODE" and len(node.args) >= 3:
            return _static_type(node.args[2], cctx)
        if n == "NVL" and node.args:
            return _static_type(node.args[0], cctx) or _static_type(node.args[-1], cctx)
        return "number"
    return None


def compile_expr(text_or_node, cctx: CompileContext | None = None):
    cctx = cctx or CompileContext()
    node = parse(text_or_node) if isinstance(text_or_node, str) else text_or_node
    return _compile(node, cctx)


def _compile(node, cctx):  # noqa: C901 - a dispatcher
    if isinstance(node, Lit):
        v = node.value
        return lambda row: v
    if isinstance(node, Ref):
        name = node.name.upper()
        if name.startswith("$$"):
            if name not in cctx.params:
                raise ExpressionError(f"undefined mapping parameter {node.name}")
            pv = cctx.params[name]
            return lambda row: pv
        if name in cctx.builtins:
            bv = cctx.builtins[name]
            return bv if callable(bv) else (lambda row: bv)
        if name in BUILTIN_CONSTANTS:
            cv = BUILTIN_CONSTANTS[name]
            return lambda row: cv
        if name == "SYSDATE":
            return lambda row: dt.datetime.now().replace(microsecond=0)
        return lambda row: row[name]
    if isinstance(node, Unary):
        f = _compile(node.operand, cctx)
        if node.op == "NOT":
            def _not(row):
                v = f(row)
                return None if v is None else (0 if truthy(v) else 1)
            return _not
        if node.op == "-":
            def _neg(row):
                v = f(row)
                return None if v is None else -_num(v)
            return _neg
        return f
    if isinstance(node, Binary):
        return _compile_binary(node, cctx)
    if isinstance(node, LkpCall):
        lk = cctx.lookups.get(node.name.upper())
        if lk is None:
            raise ExpressionError(f"unknown unconnected lookup :LKP.{node.name}")
        fargs = [_compile(a, cctx) for a in node.args]
        return lambda row: lk(*[fa(row) for fa in fargs])
    if isinstance(node, Call):
        return _compile_call(node, cctx)
    raise ExpressionError(f"cannot compile {node!r}")


def _compile_binary(node, cctx):
    lf, rf, op = _compile(node.left, cctx), _compile(node.right, cctx), node.op
    if op == "AND":
        def _and(row):
            a = lf(row)
            if a is not None and not truthy(a):
                return 0
            b = rf(row)
            if b is not None and not truthy(b):
                return 0
            if a is None or b is None:
                return None
            return 1
        return _and
    if op == "OR":
        def _or(row):
            a = lf(row)
            if a is not None and truthy(a):
                return 1
            b = rf(row)
            if b is not None and truthy(b):
                return 1
            if a is None or b is None:
                return None
            return 0
        return _or
    if op == "||":
        return lambda row: _concat(lf(row), rf(row))
    if op in ("=", "<>", "<", "<=", ">", ">="):
        import operator as _op
        fn = {"=": _op.eq, "<>": _op.ne, "<": _op.lt, "<=": _op.le, ">": _op.gt, ">=": _op.ge}[op]

        def _cmp(row):
            a, b = lf(row), rf(row)
            if a is None or b is None:
                return None
            a, b = _cmp_norm(a, b)
            return 1 if fn(a, b) else 0
        return _cmp

    def _arith(row):
        a, b = lf(row), rf(row)
        if a is None or b is None:
            return None
        if isinstance(a, dt.datetime) and op in ("+", "-") and not isinstance(b, dt.datetime):
            days = float(_num(b))
            return a + dt.timedelta(days=days if op == "+" else -days)
        if isinstance(a, dt.datetime) and isinstance(b, dt.datetime) and op == "-":
            return Decimal(str((a - b).total_seconds() / 86400))
        a, b = _num(a), _num(b)
        if op == "+":
            return a + b
        if op == "-":
            return a - b
        if op == "*":
            return a * b
        if op == "/":
            if b == 0:
                raise TransformationError("division by zero")
            return Decimal(a) / Decimal(b)
        return _mod(a, b)
    return _arith


def _compile_call(node, cctx):
    name, args = node.name, node.args
    if name == "IIF":
        if len(args) not in (2, 3):
            raise ExpressionError("IIF takes 2 or 3 arguments")
        c, t = _compile(args[0], cctx), _compile(args[1], cctx)
        if len(args) == 3:
            f = _compile(args[2], cctx)
        else:
            st = _static_type(args[1], cctx)
            default = "" if st == "string" else (None if st == "date" else 0)

            def f(row, _d=default):
                return _d

        return lambda row: t(row) if truthy(c(row)) else f(row)
    if name == "DECODE":
        if len(args) < 3:
            raise ExpressionError("DECODE takes at least 3 arguments")
        val = _compile(args[0], cctx)
        pairs = [(_compile(args[i], cctx), _compile(args[i + 1], cctx)) for i in range(1, len(args) - 1, 2)]
        default = _compile(args[-1], cctx) if len(args) % 2 == 0 else (lambda row: None)
        bool_mode = isinstance(args[0], Ref) and args[0].name.upper() == "TRUE"

        def _decode(row):
            v = val(row)
            for s, r in pairs:
                sv = s(row)
                if bool_mode:
                    if truthy(sv):
                        return r(row)
                    continue
                if v is None and sv is None:
                    return r(row)
                if v is None or sv is None:
                    continue
                a, b = _cmp_norm(v, sv)
                if a == b:
                    return r(row)
            return default(row)
        return _decode
    if name in ("SYSDATE",):
        return lambda row: dt.datetime.now().replace(microsecond=0)
    if name in cctx.builtins and not args:
        bv = cctx.builtins[name]
        return bv if callable(bv) else (lambda row: bv)
    if name in AGGREGATE_FUNCS:
        if not cctx.aggregate:
            raise ExpressionError(f"aggregate function {name} is only valid in an Aggregator")
        return _compile_aggregate(name, args, cctx)
    if name == "IN":
        val = _compile(args[0], cctx)
        opts = [_compile(a, cctx) for a in args[1:]]

        def _in(row):
            v = val(row)
            if v is None:
                return None
            for o in opts:
                ov = o(row)
                if ov is not None and _cmp_norm(v, ov)[0] == _cmp_norm(v, ov)[1]:
                    return 1
            return 0
        return _in
    fn = SIMPLE_FUNCS.get(name)
    if fn is None:
        raise ExpressionError(f"unsupported function {name}")
    fargs = [_compile(a, cctx) for a in args]
    if len(fargs) == 1:
        f0 = fargs[0]
        return lambda row: fn(f0(row))
    if len(fargs) == 2:
        f0, f1 = fargs
        return lambda row: fn(f0(row), f1(row))
    return lambda row: fn(*[fa(row) for fa in fargs])


class AggSpec:
    """An aggregate call inside an Aggregator output expression."""

    def __init__(self, name, arg, cond, star):
        self.name, self.arg, self.cond, self.star = name, arg, cond, star


def _compile_aggregate(name, args, cctx):
    star = bool(args) and isinstance(args[0], Lit) and args[0].value == "*"
    arg = None if star or not args else _compile(args[0], cctx)
    cond = _compile(args[1], cctx) if len(args) > 1 else None
    spec = AggSpec(name, arg, cond, star)
    slot = id(spec)
    cctx.agg_specs = getattr(cctx, "agg_specs", []) + [(slot, spec)]

    def _get(row):
        return row["__AGG__"][slot]
    return _get


def aggregate_specs(cctx):
    return getattr(cctx, "agg_specs", [])


class AggState:
    __slots__ = ("spec", "acc", "count", "first", "last", "vals", "seen_first")

    def __init__(self, spec):
        self.spec = spec
        self.acc = None
        self.count = 0
        self.first = None
        self.last = None
        self.vals = [] if spec.name == "MEDIAN" else None
        self.seen_first = False

    def add(self, row):
        sp = self.spec
        if sp.cond is not None and not truthy(sp.cond(row)):
            return
        if sp.star:
            self.count += 1
            return
        v = sp.arg(row)
        if v is None:
            return
        self.count += 1
        n = sp.name
        if n in ("SUM", "AVG"):
            v = _num(v)
            self.acc = v if self.acc is None else self.acc + v
        elif n == "MAX":
            self.acc = v if self.acc is None or _cmp_norm(v, self.acc)[0] > _cmp_norm(v, self.acc)[1] else self.acc
        elif n == "MIN":
            self.acc = v if self.acc is None or _cmp_norm(v, self.acc)[0] < _cmp_norm(v, self.acc)[1] else self.acc
        elif n == "FIRST":
            if not self.seen_first:
                self.first, self.seen_first = v, True
        elif n == "LAST":
            self.last = v
        elif n == "MEDIAN":
            self.vals.append(_num(v))

    def result(self):
        n = self.spec.name
        if n == "COUNT":
            return self.count
        if n == "SUM":
            return self.acc
        if n == "AVG":
            return None if not self.count else Decimal(self.acc) / self.count
        if n in ("MAX", "MIN"):
            return self.acc
        if n == "FIRST":
            return self.first
        if n == "LAST":
            return self.last
        if n == "MEDIAN":
            if not self.vals:
                return None
            s = sorted(self.vals)
            mid = len(s) // 2
            return s[mid] if len(s) % 2 else (Decimal(s[mid - 1]) + Decimal(s[mid])) / 2
        return None
