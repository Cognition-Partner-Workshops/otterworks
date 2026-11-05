# Parity harness

Run from the wave folder with Python 3.10 or later. Use two independent deployments seeded from the same SQL and input files. Reset each deployment before a replay; notification queues and document stores must start empty. HTTP requests execute in the order in `requests.json`.

```sh
python3 parity/run.py --app statements-web --vm-base http://127.0.0.1:8081/statements --kind-base http://127.0.0.1:18081 --output statements-parity.json
python3 parity/run.py --app branch-locator --vm-base http://127.0.0.1:8083 --kind-base http://127.0.0.1:18083 --output locator-parity.json
python3 parity/run.py --app notify-svc --vm-base http://127.0.0.1:8084 --kind-base http://127.0.0.1:18084 --output notify-parity.json
python3 parity/run.py --app kyc-docs --vm-base https://127.0.0.1:8085 --kind-base http://127.0.0.1:18085 --insecure-loopback --output documents-parity.json
python3 parity/run.py --app rates-batch --vm-dir /path/to/vm-spool --kind-dir /path/to/kind-spool --output rates-parity.json
python3 parity/run.py --app fx-report --vm-base http://127.0.0.1:8086 --kind-base http://127.0.0.1:18086 --output report-parity.json
```

The kind URLs are local port-forwards to that deployment's Services. Pass `--ca-file` to trust a private CA; `--insecure-loopback` accepts self-signed certificates only on loopback URLs. Export the three completed batch files from each deployment into distinct directories before comparing. The harness does not run a batch job, copy outputs between deployments or create a cluster.

The FX request selects the seeded business day `2026-10-16`. Its response contract requires that date, the rates table header and a seeded currency pair. Identical HTTP 200 missing-rate pages fail that content check; the JSON report retains the status and body-hash matches separately.

| Depth | Check | Coverage |
| --- | --- | --- |
| Status code | Both responses must match the expected status | Every request, including invalid inputs |
| Body hash per endpoint per account | SHA-256 of raw and canonical bodies retained for both paths | All 24 seeded accounts for statements, notifications and documents; six geocoder queries |
| Batch file hash per business day | SHA-256 of the whole nonempty output file | All three tick days |
| Sample values | At most 12 diff lines, only when body or file hashes differ | Mismatches only |

The harness sorts JSON object keys before comparison. It normalizes notification `at` values and the generated millisecond segment of document filenames. Raw hashes and each normalization remain in the JSON report. Document size and kind remain checked; document-content hashes require a download endpoint, which this API lacks. Invalid-account error pages are status-only because container error HTML differs between runtimes. HTML bodies otherwise compare byte-for-byte. Branch opening hours depend on the host clock; run both paths at the same time and timezone, and retain any mismatch.

Exit status is 0 only when every applicable check passes. Network failures, unexpected HTTP errors, missing or empty batch files and mismatches exit 1. Configuration errors exit 2. Unit and fake-HTTP transport checks do not prove application parity:

```sh
python3 -m unittest discover -s parity -p 'test_*.py' -v
```
