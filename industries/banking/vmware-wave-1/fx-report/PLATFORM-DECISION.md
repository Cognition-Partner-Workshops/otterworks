# Platform decision: fx-report

**Decision:** fx-report stays on **report-01 for wave 1**. Moving it is a rewrite,
not a replatform. No runtime or deployment change is made here.

Application citations below are relative to `industries/banking/vmware-wave-1/`.
Platform citations are relative to the repository root, at main commit
`19392116c2197d713811213778a7a1d75eb90cc0` (not this application branch).

## Conditions and reason

- **web-server-modules** (`complexity-manifest.json:65`): Apache runs the CGI,
  authenticates with LDAP Basic auth restricted to `fx-desk`, and caches for one
  hour (`fx-report/vm/fx-report.conf:2-15`). The page displays Apache's
  `REMOTE_USER` (`fx-report/cgi-bin/fx-report.cgi:23`). The standard chart has no
  equivalent sign-in or caching configuration: its ingress only configures
  routing and TLS (`platform/standards/helm/app/values.yaml:49-54`,
  `platform/standards/helm/app/templates/ingress.yaml:1-30`).
- **shared-filesystem** (`complexity-manifest.json:66`): input is the NFS export
  of rates-01's `/var/spool/rates/out`, mounted at `/mnt/rates-out` on report-01
  (`fx-report/HOST.md:8`). The CGI reads both the requested and previous day's
  CSV from there (`fx-report/cgi-bin/fx-report.cgi:12-19`). The chart has no PVC
  support; its volumes are only `emptyDir` and ConfigMap
  (`platform/standards/helm/app/templates/_helpers.tpl:71-93`).
- **eol-runtime** (`complexity-manifest.json:67`): the host uses RHEL 6,
  system Perl 5.10 and Apache 2.2 (`fx-report/HOST.md:5`). The approved image
  list has neither Perl nor Apache httpd
  (`platform/standards/base-images.yaml:4-42`), so retaining the httpd/Perl
  image (`fx-report/vm/Dockerfile:4-5`) cannot pass BASE-01's exact approved
  image check (`platform/standards/policy/conftest/dockerfile.rego:20-28`).
- **Host-zone dependency:** without a `day` parameter, the business date uses
  `localtime(time - 86400)`, so the host time zone affects the result
  (`fx-report/cgi-bin/fx-report.cgi:13`).

## Coupling to rates-batch

rates-batch is moving to the platform in a parallel PR (coordination requirement,
not a change in this branch). Whatever it writes must still land at
`/mnt/rates-out` on report-01 as `rates-<day>.csv`, unchanged. Preserve the
`pair,open,high,low,close,avg_mid,ticks` CSV format and previous-day availability:
the producer writes that header and filename
(`rates-batch/src/main/java/com/bank/rates/RatesJob.java:82-89`), and the consumer
opens both days and parses those columns positionally
(`fx-report/cgi-bin/fx-report.cgi:18-19`, `fx-report/lib/FxReport/Rates.pm:7-19`).
The current NFS handoff is documented in `rates-batch/vm/run-rates.sh:2-7` and
`fx-report/HOST.md:8`; the stand-in models it with a shared volume
(`vm/compose.yaml:39-49`). Changing the producer's store alone is not sufficient.

## What a rewrite would need

- Port `Rates.pm` and the CGI to an approved runtime, for example
  `python-3.12-slim` (`fx-report/lib/FxReport/Rates.pm:7-32`,
  `fx-report/cgi-bin/fx-report.cgi:1-35`, `platform/standards/base-images.yaml:22-25`).
- Replace LDAP Basic auth with ingress/IdP sign-in, preserving desk authorization
  and user identity (`fx-report/vm/fx-report.conf:9-13`,
  `fx-report/cgi-bin/fx-report.cgi:23`); this requires integration beyond the
  current chart's routing/TLS settings cited above.
- Read rates from the store rates-batch publishes to instead of the NFS path
  (`fx-report/cgi-bin/fx-report.cgi:12-19`).
- Emit a `Cache-Control` header instead of relying on `mod_expires` for the
  one-hour policy (`fx-report/vm/fx-report.conf:14-15`,
  `fx-report/cgi-bin/fx-report.cgi:21`).
- Specify an explicit business-date zone rather than the host-local default
  (`fx-report/cgi-bin/fx-report.cgi:13`).

## Risk of staying

RHEL 6, Perl 5.10 and Apache 2.2 are end of life; retaining the VM retains that
support and security risk (installed versions: `fx-report/HOST.md:5`;
estate classification: `complexity-manifest.json:62-67`). The smoke test only
checks the stand-in: it uses httpd 2.4 and omits LDAP, not the production stack
(`fx-report/vm/Dockerfile:1-7`, `fx-report/HOST.md:12`).
