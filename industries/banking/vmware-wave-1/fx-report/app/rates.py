"""Port of FxReport::Rates (lib/FxReport/Rates.pm): read a rates-batch day file and work out day-on-day moves.

Close and avg stay the CSV strings (the report prints them verbatim); range and change are IEEE doubles,
like Perl NVs, and are formatted with format_range / format_change exactly as fx-report.cgi does.
"""
import re

COLUMNS = ("pair", "open", "high", "low", "close", "avg", "ticks")
_NUMERIC_PREFIX = re.compile(r"\s*([+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)", re.ASCII)  # Perl reads bytes


def perl_num(value):
    """A value in numeric context, as Perl numifies it: numbers as they are, undef and non-numeric
    text 0, otherwise the leading number of the text ("0.66x" -> 0.66)."""
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    m = _NUMERIC_PREFIX.match(value)
    return float(m.group(1)) if m else 0.0


def read_day(path):
    """Rates per pair from one rates-batch file, or None when it cannot be opened.

    The header line is skipped whatever it says, empty lines are skipped, fields are split on commas
    with trailing empty fields dropped (Perl split), missing fields are None and a repeated pair keeps
    its last line.
    """
    try:
        fh = open(path, encoding="utf-8", errors="surrogateescape", newline="\n")  # noqa: SIM115 (closed below)
    except IsADirectoryError:
        return {}  # Perl opens a directory and reads no lines
    except OSError:
        return None
    rates = {}
    with fh:
        fh.readline()
        for line in fh:
            line = line.removesuffix("\n")
            if not line:
                continue
            fields = line.split(",")
            while fields and fields[-1] == "":
                fields.pop()
            fields += [None] * (len(COLUMNS) - len(fields))
            values = dict(zip(COLUMNS, fields))
            pair = values.pop("pair") or ""
            rates[pair] = values
    return rates


def moves(today, prev):
    """One row per pair of today, sorted by pair: close and avg verbatim, range = high - low and
    chg_pct = (close - prev close) / prev close * 100, None when prev or the pair in prev is missing."""
    rows = []
    for pair in sorted(today):
        t = today[pair]
        p = prev.get(pair) if prev is not None else None
        chg = None
        if p is not None:
            prev_close = perl_num(p.get("close"))
            chg = (perl_num(t.get("close")) - prev_close) / prev_close * 100
        rows.append({"pair": pair, "close": t.get("close"), "avg": t.get("avg"),
                     "range": perl_num(t.get("high")) - perl_num(t.get("low")), "chg_pct": chg})
    return rows


def format_range(value):
    return "%.5f" % value  # noqa: UP031 (same printf format as fx-report.cgi)


def format_change(value):
    return "n/a" if value is None else "%+.3f%%" % value  # noqa: UP031
