"""Compare two gateway-stub request logs (--log output) from the same scripted UI run.

Ids, tokens and timestamps differ between runs, so each line is reduced to what the
client controls: method, path, query, whether a bearer token was sent, the content type
and the request body. Prints one row per request and exits non-zero on any difference.
"""

import json
import sys


def load(path):
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                r = json.loads(line)
                rows.append((r["method"], r["path"], json.dumps(r["query"], sort_keys=True),
                             r["authorization"] or "-", r["content_type"] or "-",
                             json.dumps(r["body"], sort_keys=True), r["status"]))
    return rows


def main(before_path, after_path):
    before, after = load(before_path), load(after_path)
    failed = 0
    print("| # | request | before | after | result |")
    print("|---|---|---|---|---|")
    for i in range(max(len(before), len(after))):
        b = before[i] if i < len(before) else None
        a = after[i] if i < len(after) else None
        name = "%s %s" % ((b or a)[0], (b or a)[1])
        same = b == a
        failed += not same
        fmt = lambda r: "missing" if r is None else "%s %s body=%s -> %s" % (r[3], r[2], r[5], r[6])
        print("| %d | %s | %s | %s | %s |" % (i + 1, name, fmt(b), fmt(a), "identical" if same else "FAILED"))
    print("\n%d of %d requests identical" % (max(len(before), len(after)) - failed, max(len(before), len(after))))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
