# admin-service: patch-level gem security updates

`bundle lock --conservative --update` for crass 1.0.6→1.0.8, loofah 2.25.1→2.25.3, mail 2.9.0→2.9.1, msgpack 1.8.0→1.8.7, net-imap 0.6.4→0.6.8, nokogiri 1.19.3→1.19.7, rack 3.2.6→3.2.8 and rails-html-sanitizer 1.7.0→1.7.2. No Gemfile constraint changed.

| image | total | CRITICAL | HIGH | MEDIUM | LOW | UNKNOWN | Ruby gems | Debian OS |
|---|---|---|---|---|---|---|---|---|
| baseline (sha256:faf793c1a317…) | 532 | 4 | 145 | 195 | 180 | 8 | 105 | 427 |
| after (sha256:3568ca6662e8…) | 482 | 4 | 140 | 170 | 164 | 4 | 55 | 427 |

Scanner: Trivy 0.71.0, vulnerability DB v2 UpdatedAt 2026-11-13 12:56:33 UTC (the same DB was used for every scan, with --skip-db-update). Base image ruby:3.3-slim@sha256:db3ad6dd68a886d51a187fb9bf486052f2976cdbe3b750169c25092aba1297fa (Debian 13.7, Ruby 3.3.13).
Images were built locally from services/admin-service (`docker build -t admin-service:<tag> .`). They are not the images deployed from ECR to otterworks-ciso, which could not be read: no AWS/kube credentials.

Reproduce:
```
trivy image --download-db-only --cache-dir ~/.cache/trivy-admin
trivy image --cache-dir ~/.cache/trivy-admin --skip-db-update --scanners vuln --ignorefile /dev/null \
  --severity UNKNOWN,LOW,MEDIUM,HIGH,CRITICAL -f json -o <name>.json admin-service:<tag>
```
`*.trivy.min.json` is the Trivy JSON output trimmed with jq to ImageID/OS and, for each finding: VulnerabilityID, PkgName, InstalledVersion, FixedVersion, Status, Severity, PkgPath. No findings were removed. No .trivyignore was used.
