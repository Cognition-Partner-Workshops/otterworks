# statements-web parity

- Decision: move; standards pinned at `19392116c2197d713811213778a7a1d75eb90cc0`.
- **65/65 cases equal**: HTTP status, Content-Type and raw body bytes.
- Normalisations: **none**. Date/connection headers are not comparison fields. Independent cookie jars retain each side's own state; generated cookie IDs are not body values.
- Seed SHA-256: `d0a85dd227832fd10b71cbaebb9ee4efe0fc38e257293f0eb9be444cdf613756`.
- The kind ConfigMap contains exactly the original `data/seed.sql` bytes (asserted before comparison).
- VM baseline: untouched `origin/demo-bank` at `ae25fcdbeb86b4289fc6bc6fd11dfa350fb8a8da`, image ID `sha256:d971d4eccacffe0a4a3d69c4e08aba1422c0b33c5a6dfef4306d9305a7d2ff18`.
- Container: image ID `sha256:bcac2d59979f113c94bb1e6e21a588f574450ec04ecdef6379f3104352a966ae`; Tomcat 9.0.123 / JRE 8. Both sides use effective UTC, en_US and UTF-8.

## Cases

| Cases | Count | Equal |
|---|---:|---:|
| Fresh accounts | 1 | 1 |
| Statements for every seeded account | 24 | 24 |
| Last viewed after every seeded account | 24 | 24 |
| Unknown valid account + Last viewed (legacy empty 200 page) | 2 | 2 |
| Missing, empty, bad and encoded-invalid account + unchanged Last viewed | 8 | 8 |
| Index and index.html | 2 | 2 |
| Statement on pod A → accounts on pod B, then the reverse with another account | 4 | 4 |
| **Total** | **65** | **65** |

The two direct pod port-forwards target distinct pods `statements-web-5c74848769-47tjm` and `statements-web-5c74848769-h5rj6` (both Ready). The cross-replica suite asserts the VM still creates JSESSIONID and the platform does not. `transcript.json` records both sides' status, content-type and SHA-256 per case; the script also writes raw `.body` and status/type `.json` files under the ignored run directory.

## Gate and additional regression evidence

| Step | Result |
|---|---|
| Full untouched `make vm-build && make vm-up && make vm-smoke` | Pass: all six services; three rates output files |
| Rebuild statements using the unchanged `vm/Dockerfile` and migrated source | Pass; another **61/61** byte-equal cases against the untouched VM, preserving the fallback |
| `docker build --target test` (Java 8 compilation + JUnit) | **7 tests**, no failures/errors/skips |
| Container build | Pass |
| Pinned `policy-check.sh` | **48/48** checks |
| Pinned `kind-verify.sh`, `KIND_CLUSTER=w1-statements-web` | Pass: Kyverno Enforce, two replicas, all four smoke paths |
| Trivy 0.73.0 vuln+secret, CRITICAL fixed | Pass: zero findings |
| Trivy 0.73.0 secret, HIGH/CRITICAL | Pass: zero findings |
| Syft 1.14.0 SPDX JSON | Pass |
| Python flake8 / py_compile; git diff --check | Pass |
| Database outage then recovery | `/health`: **200 → 503 → 200** |
| Database role | SELECT allowed; INSERT/UPDATE/DELETE, superuser, createdb and createrole all false |
| Runtime security | uid/gid 10001; write to root rejected as read-only; no Tomcat deployment/log file writes |

`runtime-checks.json` records the health transition, final two-replica deployment status and role query.

## Reproduce

Keep the untouched VM stack running in a separate checkout. Set `MAVEN_MIRROR=https://maven-central.storage-download.googleapis.com/maven2/` for the VM build if required. Use the pinned main checkout for all standards commands:

```sh
APP=/path/to/app-checkout/industries/banking/vmware-wave-1/statements-web
STD=/path/to/pinned-main/platform/standards
IMG=599083837640.dkr.ecr.us-east-1.amazonaws.com/otterworks/bank-statements-web
docker build --target test "$APP"
docker build -t "$IMG:local-final" "$APP"
"$STD/scripts/policy-check.sh" "$APP" "$IMG" local-final
KIND_CLUSTER=w1-statements-web "$STD/scripts/kind-verify.sh" "$APP" "$IMG" local-final
trivy image --scanners vuln,secret --secret-config "$STD/policy/trivy/secret-rules.yaml" --severity CRITICAL --ignore-unfixed --exit-code 1 "$IMG:local-final"
trivy image --scanners secret --secret-config "$STD/policy/trivy/secret-rules.yaml" --severity HIGH,CRITICAL --exit-code 1 "$IMG:local-final"
```

In three terminals, port-forward the Service to 18081 and the two distinct pods to 18082/18083; do not forward both replica ports to the same pod:

```sh
kubectl -n app-statements-web port-forward svc/statements-web 18081:80
kubectl -n app-statements-web port-forward pod/<pod-A> 18082:8080
kubectl -n app-statements-web port-forward pod/<pod-B> 18083:8080
python3 "$APP/parity/compare.py" --vm http://127.0.0.1:8081 \
  --candidate http://127.0.0.1:18081 \
  --replica http://127.0.0.1:18082 --replica http://127.0.0.1:18083
```

For a VM-only capture, omit candidate/replica arguments and set `--out "$APP/parity/baseline"`.

The statements VM is HTTP, unlike kyc-docs; no TLS normalisation or insecure TLS option is needed. The exact legacy invalid-account body includes the old Tomcat footer by design, not because the container is running Tomcat 8.5.

## Rollout decisions

Preserve the observed UTC/locale and legacy error page. Product may later change these through a separate behaviour change. Kind's throwaway PostgreSQL fixture uses trust authentication and a SELECT-only role, with a scoped NetworkPolicy; the synthetic app secret demonstrates chart wiring, not production authentication. Production must provision the password-authenticated backing service/reader role and External Secret named `statements-db` before using real connection settings. No AWS resources were created and EKS deployment is disabled.
