# admin-service: drop unused Rails frameworks from the image

The Gemfile now lists the Rails component gems that config/application.rb loads, instead of the `rails` meta-gem. activestorage, actioncable, actionmailbox, actiontext, websocket-driver, websocket-extensions and marcel are no longer installed in the image.

| image | total | CRITICAL | HIGH | MEDIUM | LOW | UNKNOWN | Ruby gems | Debian OS |
|---|---|---|---|---|---|---|---|---|
| baseline (sha256:faf793c1a317…) | 532 | 4 | 145 | 195 | 180 | 8 | 105 | 427 |
| after (sha256:6f830c68d3c7…) | 508 | 0 | 138 | 186 | 176 | 8 | 81 | 427 |

All 4 CRITICAL findings (activestorage 7.1.6: CVE-2026-122006, CVE-2026-33195, CVE-2026-33202, GHSA-f3w6-w445-fwh9) are gone because the package is no longer in the image.

Scanner: Trivy 0.71.0, vulnerability DB v2 UpdatedAt 2026-11-13 12:56:33 UTC (the same DB was used for every scan, with --skip-db-update). Base image ruby:3.3-slim@sha256:db3ad6dd68a886d51a187fb9bf486052f2976cdbe3b750169c25092aba1297fa (Debian 13.7, Ruby 3.3.13).
Images were built locally from services/admin-service (`docker build -t admin-service:<tag> .`). They are not the images deployed from ECR to otterworks-ciso, which could not be read: no AWS/kube credentials.

Reproduce:
```
trivy image --download-db-only --cache-dir ~/.cache/trivy-admin
trivy image --cache-dir ~/.cache/trivy-admin --skip-db-update --scanners vuln --ignorefile /dev/null \
  --severity UNKNOWN,LOW,MEDIUM,HIGH,CRITICAL -f json -o <name>.json admin-service:<tag>
```
`*.trivy.min.json` is the Trivy JSON output trimmed with jq to ImageID/OS and, for each finding: VulnerabilityID, PkgName, InstalledVersion, FixedVersion, Status, Severity, PkgPath. No findings were removed. No .trivyignore was used.
