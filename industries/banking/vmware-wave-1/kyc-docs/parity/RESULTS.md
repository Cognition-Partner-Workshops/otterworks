# KYC document HTTP and stored-byte parity

## Result

23/23 cases match the original VM on the platform container, and 23/23 match
on the rebuilt branch VM. Status, Content-Type and UTF-8 response body bytes
are compared, including JSON property order, whitespace, list order and
Tomcat's HTML response for an encoded slash. No JSON sorting or reserialization
is applied to response bodies.

All 10 stored objects on each of the original VM, branch VM and Moto match the
deterministic fixture SHA-256 values (30/30 object checks). The expected object
set is also checked: extra or missing objects fail verification.

Captured on 2026-11-05, branch `devin/1793883197-bank-w1-kyc-docs`, working
changes based on `origin/demo-bank` at
`ae25fcdbeb86b4289fc6bc6fd11dfa350fb8a8da`.

| Side | Image | Image ID |
|---|---|---|
| Original | wave1/kyc-docs-vm:before-demo-bank | sha256:1eb319dbe92ea1a96677292195e57853cbc8d3e2981ff7c16358c3da977a36a1 |
| Platform | 599083837640.dkr.ecr.us-east-1.amazonaws.com/otterworks/bank-kyc-docs:local | sha256:5c9a61a032b814bca59f4728f3a2d5b62ecb6d63a64e96082f9fc52544506f67 |
| Branch VM | wave1/kyc-docs-vm:latest | sha256:60f2ff21b2cfe0dc4d452ecf649a3790df218ffd3e19d37bf16e36ca507ef7d2 |

Original VM and platform use `TZ=Etc/UTC`. The unmodified branch compose
configuration uses its image's system timezone: `/etc/localtime` resolves to
`/usr/share/zoneinfo/Etc/UTC`, and `date +%Z` prints `UTC`.

The platform uses Boot 4.0.9 / Spring Framework 7.0.9 / Tomcat 11.0.25 / AWS SDK
2.57.8; the VM retains Boot 2.3.12.RELEASE and Java 11. Moto is the ephemeral,
in-memory `mirror.gcr.io/motoserver/moto:5.1.0` fixture.

## Allowed normalisations (only these)

1. In generated filenames, `(passport|id-card|proof-of-address|payslip)-[0-9]{13}\.`
   becomes the same kind followed by `-<millis>.`.
2. Within the exact `"timestamp":"..."` field, each ASCII digit becomes `0`.
   Punctuation, timezone syntax, precision and field presence remain unchanged.

The same filename substitution applies inside list bodies, without changing
their order. Headers/statuses receive no normalisation.

## Per-case results

Both equality columns include status, content type and normalised body bytes.

| Case | Status (all three) | Content-Type (all three) | VM vs platform | VM vs branch VM |
|---|---:|---|---|---|
| HG611000001-passport | 201 | application/json | PASS | PASS |
| HG611000001-id-card | 201 | application/json | PASS | PASS |
| HG611000001-proof-of-address | 201 | application/json | PASS | PASS |
| HG611000001-payslip | 201 | application/json | PASS | PASS |
| HG621000002-passport | 201 | application/json | PASS | PASS |
| HG621000002-id-card | 201 | application/json | PASS | PASS |
| HG621000002-proof-of-address | 201 | application/json | PASS | PASS |
| HG621000002-payslip | 201 | application/json | PASS | PASS |
| lowercase-id | 400 | application/json | PASS | PASS |
| short-id | 400 | application/json | PASS | PASS |
| path-id | 400 | text/html;charset=utf-8 | PASS | PASS |
| unknown-kind | 400 | application/json | PASS | PASS |
| exe-extension | 201 | application/json | PASS | PASS |
| no-extension | 201 | application/json | PASS | PASS |
| missing-kind | 400 | application/json | PASS | PASS |
| missing-file | 400 | application/json | PASS | PASS |
| non-multipart | 500 | application/json | PASS | PASS |
| list-first | 200 | application/json | PASS | PASS |
| list-second | 200 | application/json | PASS | PASS |
| list-empty | 200 | application/json | PASS | PASS |
| list-bad-id | 400 | application/json | PASS | PASS |
| documents-root | 404 | application/json | PASS | PASS |
| trailing-slash | 200 | application/json | PASS | PASS |

The intentionally preserved non-multipart response is 500, not a redesigned
400 response. The seeded, upload-free customer is HG631000003.

## Fixes discovered by parity

- `PlatformErrorAttributes` retains the VM's empty `message` field and its
  property position before `path`. It formats error timestamps with exactly
  three fractional digits and `+00:00`, rather than Jackson 3's `Z`.
- `PlatformTrailingSlashController` restores trailing-slash document routes
  without changing the shared Java 11 controller or the VM build.
- Stored-byte checking exposed Moto storing AWS signed chunk frames and
  checksum trailers as part of file contents. The S3 client now sends
  non-chunked requests and calculates optional request checksums only when
  required. Disabling chunking exposed non-resettable multipart streams during
  signing; uploads now use a temporary file under writable `/tmp`, with
  actual byte-count validation and deletion in `finally`. This bounds heap
  usage, makes signing/retries repeatable and returns the bytes actually stored.
  A real local HTTP-server unit test exercises the non-markable-stream path and
  verifies the exact bytes transmitted, not just a mocked SDK call.

All fixes are in platform sources/tests; `pom.xml`, VM files, seed data,
platform standards and the user's workflow changes were not edited.

## Seed and fixture hashes

`../data/seed.sql` SHA-256:
`d0a85dd227832fd10b71cbaebb9ee4efe0fc38e257293f0eb9be444cdf613756`

Fixtures are generated as byte literals in `parity.py`, not read from external
files. The four document-type fixtures have distinct sizes.

| Fixture | Bytes | SHA-256 |
|---|---:|---|
| passport.pdf | 38 | cefdaf4ca297dbb141aab7d67e39b56b199535290e176531cf3c0b03835fac4c |
| id-card.jpg | 26 | 7b1a42da65cb5c3721455c362e407a3016a079cc6d1c734f04274f7d07213aa0 |
| address.png | 39 | aa98665a47616f170d4a617803767a5f600ba91df02336855533784bbd1a47b6 |
| payslip.JPEG | 46 | 6f4ed866e1aafbe56917e695ae337f92d2b23c5d24804cfb8a119a0ddbcc286e |
| notes.exe | 38 | a0afb165cfda703b0e20b90d9e44e5fca2c296f94992b386760a6c23e552842f |
| no-extension | 29 | 3199a8cbab59e34521ac9d11b1d55dcb07ba031ac7019d142cb63380be753584 |

`out/storage-check.json` records expected and actual normalised key/hash maps
for all three sides, plus original S3 keys. The two raw VM sha256sum captures
are retained in `out/*.sha256`.

## Cross-replica verification

Final platform capture alternated every request between:

- pod A: `kyc-docs-645448f4f5-h4rtl` on localhost:18081;
- pod B: `kyc-docs-645448f4f5-zfsmt` on localhost:18082.

Both customer lists contain uploads handled by both pods. A separate service
port-forward on localhost:18080 also answered /health 200. Storage was reset
by restarting Moto before the final capture; old application pods were replaced.

## Commands

These are the commands used (port-forwards/readiness and cleanup were managed
with Python subprocesses; shell equivalents are shown). Paths assume the repo
at `/home/ubuntu/repos/otterworks`.

```bash
APP=/home/ubuntu/repos/otterworks/industries/banking/vmware-wave-1/kyc-docs
WAVE=/home/ubuntu/repos/otterworks/industries/banking/vmware-wave-1
STD=/home/ubuntu/otw-main/platform/standards
IMG=599083837640.dkr.ecr.us-east-1.amazonaws.com/otterworks/bank-kyc-docs
MIRROR=https://maven-central.storage-download.googleapis.com/maven2/

# Fresh original VM; wait for /documents/HG611000001 to answer 200.
docker rm -f wave1-vm-kyc-01-1
docker run -d --name kyc-before -e TZ=Etc/UTC -p 127.0.0.1:8085:8443 wave1/kyc-docs-vm:before-demo-bank
python3 "$APP/parity/parity.py" --base https://localhost:8085 --insecure --out "$APP/parity/out/vm"
docker exec kyc-before find /var/kyc/uploads -type f -exec sha256sum {} + > "$APP/parity/out/vm-stored.sha256"

docker build --progress=plain --build-arg MAVEN_MIRROR="$MIRROR" --target test "$APP"
docker build --progress=plain --build-arg MAVEN_MIRROR="$MIRROR" -t "$IMG:local" "$APP"
kind load docker-image "$IMG:local" --name w1-kyc-docs
kubectl rollout restart deployment/s3 -n deps
kubectl rollout status deployment/s3 -n deps --timeout=120s
kubectl rollout restart deployment/kyc-docs -n app-kyc-docs
kubectl rollout status deployment/kyc-docs -n app-kyc-docs --timeout=120s
kubectl port-forward -n app-kyc-docs pod/kyc-docs-645448f4f5-h4rtl 18081:8080 &
PF_A=$!
kubectl port-forward -n app-kyc-docs pod/kyc-docs-645448f4f5-zfsmt 18082:8080 &
PF_B=$!
kubectl port-forward -n app-kyc-docs svc/kyc-docs 18080:80 &
PF_SVC=$!
# Wait for all three forwarded /health endpoints to answer 200.
python3 "$APP/parity/parity.py" --base http://localhost:18081 --base http://localhost:18082 --out "$APP/parity/out/container"
kill "$PF_A" "$PF_B" "$PF_SVC"
python3 "$APP/parity/compare.py" "$APP/parity/out/vm" "$APP/parity/out/container"

# Whole-wave VM checks. Run these make commands in $WAVE.
docker stop kyc-before
cd "$WAVE"
MAVEN_MIRROR="$MIRROR" make vm-build
MAVEN_MIRROR="$MIRROR" make vm-up
MAVEN_MIRROR="$MIRROR" make vm-smoke
docker compose -f vm/compose.yaml up -d --force-recreate kyc-01
# Wait for HTTPS /documents/HG611000001 to answer 200.
python3 "$APP/parity/parity.py" --base https://localhost:8085 --insecure --out "$APP/parity/out/vm-branch"
python3 "$APP/parity/compare.py" "$APP/parity/out/vm" "$APP/parity/out/vm-branch"
docker exec wave1-vm-kyc-01-1 find /var/kyc/uploads -type f -exec sha256sum {} + > "$APP/parity/out/vm-branch-stored.sha256"
make reset

python3 "$APP/parity/verify_storage.py" --vm-sha "$APP/parity/out/vm-stored.sha256" --vm-branch-sha "$APP/parity/out/vm-branch-stored.sha256" --out "$APP/parity/out/storage-check.json"
# This helper runs boto3 list/get inside deployment/s3; local Python is stdlib-only.
sha256sum "$WAVE/data/seed.sql"
cd "$APP/parity"
python3 -m unittest -v test_parity

"$STD/scripts/policy-check.sh" "$APP" "$IMG" local
KIND_CLUSTER=w1-kyc-docs OUT=/home/ubuntu/scratch/kyc-trivy/kind-verify "$STD/scripts/kind-verify.sh" "$APP" "$IMG" local
trivy image --scanners vuln,secret --secret-config "$STD/policy/trivy/secret-rules.yaml" --severity CRITICAL --ignore-unfixed "$IMG:local"
```

## Post-fix checks

- Platform test-stage build: 14 tests, 0 failures/errors/skips; BUILD SUCCESS.
- Parity script unit tests: 3 tests, OK.
- Policy: Dockerfile 4/4 and manifests 33/33 passed, no warnings/failures.
- Kind smoke: /health 200, valid customer list 200, bad customer list 400;
  `{"app":"kyc-docs","stage":"smoke","status":"pass","detail":"all smoke paths answered"}`.
- Trivy CRITICAL with ignore-unfixed: Ubuntu 22.04 = 0, JAR = 0; no secret
  findings listed (Trivy prints '-' in its secret-summary cells).
- Whole-wave vm-build, vm-up, vm-smoke exited 0. Smoke statuses: statements
  200, branch locator 200, notify 202, KYC 200, FX report 200; all three rates
  output files present. `make reset` completed.
- The kind cluster is retained. Original `kyc-before` is stopped; the branch
  compose stack and its volume were removed by reset.

## Evidence retention

Keep `out/` with the scripts and this report: all 69 small per-case JSON
captures, three ordered indexes/fixture manifests, and storage hashes are
synthetic and useful as audit evidence. No credentials are in these captures.
Nothing has been committed yet, following the instruction to hold commits.
