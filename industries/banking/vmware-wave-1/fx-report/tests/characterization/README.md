# fx-report characterization tests

Pin what the Perl CGI report shows, so the rewrite can be held to it. Each test requests a page from a running
report, parses it (`report_page.py`: title, heading, business-date line, empty-day message, table columns and every
cell of Pair, Close, Average mid, Range, Change) and compares the parsed values with the golden pages in
`../golden/`. Markup is not compared, so CGI.pm's XHTML wrapper is not part of the contract. HTTP status and
`Content-Type` (spaces/case ignored) are compared with the golden `.headers`.

```sh
pip install pytest==8.3.5            # Python 3.12, stdlib otherwise
cd industries/banking/vmware-wave-1/fx-report/tests
BASE_URL=http://localhost:8086 python3 -m pytest -v characterization
```

| Variable | Default | Meaning |
|---|---|---|
| `BASE_URL` | required | scheme://host:port of the report under test |
| `REPORT_PATH` | `/fx/fx-report.cgi` | request path; the cases append `?day=...` |
| `REPORT_TZ` | `UTC` | zone the report under test uses for "yesterday" (the stand-in has no `TZ`) |

The same tests run unchanged against the new service; only the variables change.

## Accepted differences

Listed in `ACCEPTED_DIFFERENCES` in `test_report_pages.py`, each with its reason; nothing else may differ.

- `no-day`: the golden page was captured on 2026-10-20 UTC and shows 2026-10-19; the test expects yesterday in
  `REPORT_TZ` instead.

## Evidence

`evidence/perl-standin.txt`: 12 passed against the Perl stand-in (`make vm-build && make vm-up`, see
`../golden/README.md` for the mirror commands). Negative checks run at the same time (not kept as files):
`REPORT_TZ=Pacific/Kiritimati` fails `no-day` (`'FX desk report 2026-10-19' == 'FX desk report 2026-10-20'`), and a
`REPORT_PATH` forcing `?day=2026-10-15` fails the 2026-10-16 case.
