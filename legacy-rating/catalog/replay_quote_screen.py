from concurrent.futures import ThreadPoolExecutor
from html import unescape
from pathlib import Path
import re
from urllib.parse import urlencode
from urllib.request import urlopen


def overpunch(value):
    last = value[-1]
    if last.isdigit():
        return int(value)
    if last in "{ABCDEFGHI":
        return int(value[:-1] + str("{ABCDEFGHI".index(last)))
    return -int(value[:-1] + str("}JKLMNOPQR".index(last)))


def replay(record):
    fields = {
        "line": record[8:10], "state": record[10:12], "class": record[12:17].strip(),
        "territory": record[17:20], "effective": record[20:28],
        "exposure": f"{overpunch(record[28:37]) / 100:.2f}",
        "years": record[37:39], "claims": record[39:41], "deductible": record[41:46],
        "schedule": overpunch(record[47:50]), "addl": record[50:52],
    }
    for name, index in (("multi", 46), ("equipment", 52), ("waiver", 53), ("hnoa", 54)):
        if record[index] == "Y":
            fields[name] = "on"
    with urlopen("http://127.0.0.1:8091/?" + urlencode(fields), timeout=20) as response:
        html = response.read().decode("utf-8")
    quote = dict((name, unescape(value)) for name, value in
                 re.findall(r"<tr><td>([^<]+)</td><td>([^<]*)</td></tr>", html))
    money = [str(int(quote[name].removeprefix("$").replace(".", ""))) for name in
             ("Base premium", "Modified premium", "Endorsements", "Policy fee", "Total")]
    status, _, reason = quote["Status"].strip().partition(" ")
    minimum = {"yes": "Y", "no": "N"}[quote["Minimum applied"]]
    return [record[:8], status, reason, *money[:2], minimum, *money[2:], quote["Factor source"]]


def main():
    root = Path(__file__).resolve().parents[1]
    fixtures = (root / "fixtures/policies.dat").read_text().splitlines()
    batch = [line.split("|") for line in (root / "build/pharo.txt").read_text().splitlines()]
    expected = {row[0]: row for row in batch}
    if len(fixtures) != 200 or len(batch) != 200 or {row[:8] for row in fixtures} != expected.keys() or len(expected) != 200:
        raise SystemExit("Expected 200 distinct and identical fixture and Pharo batch policy IDs")
    with ThreadPoolExecutor(max_workers=10) as pool:
        for row in pool.map(replay, fixtures):
            if row != expected[row[0]]:
                raise SystemExit(f"{row[0]}: screen {row[1:]!r} != batch {expected[row[0]][1:]!r}")
    print("PHARO SCREEN: 200/200 policy IDs and all eight displayed fields match Pharo batch")


if __name__ == "__main__":
    main()
