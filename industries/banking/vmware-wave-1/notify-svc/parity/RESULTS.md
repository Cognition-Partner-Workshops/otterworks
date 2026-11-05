# notify-svc VM/platform parity

- Date: 2026-11-05 (UTC); recorded at 13:06:23Z.
- Standard: `19392116c2197d713811213778a7a1d75eb90cc0`.
- Result: **52 cases, 52 PASS, 0 FAIL** (status, content-type, body bytes).
- Seed: `industries/banking/vmware-wave-1/data/seed.sql`.
- Seed SHA-256: `d0a85dd227832fd10b71cbaebb9ee4efe0fc38e257293f0eb9be444cdf613756`.
- Accounts: HG621000002, HG631000003, HG641000004, HG651000005,
  HG661000006, HG671000007, HG681000008 (dedicated rate account),
  1234 (short), HG000000000 (unknown).
- The smoke account HG611000001 is neither read nor written by parity.

## Capture/reset

Run from `industries/banking/vmware-wave-1`:

```sh
python3 notify-svc/parity/parity.py --base http://localhost:8084 \
  --out notify-svc/parity/captures/vm \
  --reset-cmd 'docker compose -f vm/compose.yaml up -d --force-recreate notify-01'
python3 notify-svc/parity/run-kind.py --out notify-svc/parity/captures/platform
python3 notify-svc/parity/parity.py compare \
  notify-svc/parity/captures/vm notify-svc/parity/captures/platform
```

VM recreation resets its in-container Redis. The capture waits for GET readiness
and verifies all nine account outboxes are exactly `[]` before sending cases.

The kind wrapper restarts `deps/deploy/redis`, waits for rollout completion,
starts fresh port-forwards, and waits for `/health` 200 on every upstream. Redis
has persistence disabled. It then invokes capture with `--reset-cmd true` because
the wrapper already performed the reset. Capture independently verifies the same
nine empty outboxes. Port-forwards are closed when capture finishes; the cluster
and workloads remain running.

A Service port-forward pins one pod rather than balancing traffic. To exercise
both replicas, the wrapper rotates requests between the Service port-forward
and direct port-forwards to each pod through a local stdlib HTTP proxy. It
preserves request headers, status, content-type, and raw response body bytes.
`captures/platform/routing.tsv` records every request/upstream/status, including
the initial clean-store checks. Forward logs and both pod logs are also captured.

The sole normalization is raw-byte regex replacement of outbox JSON
`"at":"<ISO timestamp>"` with `"at":"<AT>"` during comparison. No JSON
re-serialization or other normalization is performed. There are **28 replacements
per capture**: 2 + 1 + 1 + 1 + 1 + 1 + 20 + 1 + 0 across the nine outboxes.
Original bytes remain in `cases.json` as base64. `/health` is not a parity case.
Timezone configuration was not changed: timestamps use `Date.toISOString()`
(UTC regardless of TZ); no other output depends on timezone.

## Two-replica / shared rate-limit evidence

| Pod | Total queued lines | Rate account queued lines |
| --- | ---: | ---: |
| notify-svc-6c8ddfcd95-jvn65 | 9 | 7 |
| notify-svc-6c8ddfcd95-lhr4x | 19 | 13 |

Both pod logs contain `queued card_payment for ****0008`. The first 20 rate
requests return 202 across both replicas. The 21st returns 429 through the
Service forward; the 22nd returns 429 through the jvn65 pod forward. Both bodies
are exactly `{"error":"rate limited"}`. The rate outbox has exactly 20 entries,
newest first. See the ordered cases and routing evidence.

## Image/container identities

- VM image: `wave1/notify-svc-vm:latest`, ID
  `sha256:07a6b2e3173a956d5cc116a6ed8821242692e62e432e2945abc3d5c0c3e7b28e`.
- VM container: `875a894f3cc09bc860d7248103838cd87766c21c391811d2a51c2371d12dcd19`.
- Platform image: `599083837640.dkr.ecr.us-east-1.amazonaws.com/otterworks/bank-notify-svc:local`.
- Docker image index ID: `sha256:fff013bd15fc09497944ab8d85042f2d7c320d8e445d3dedc981e546304a8ef2`.
- Both kind pods' image manifest: `sha256:f5343c4a5cf76a1d3a57ab8cc31d6d56dd965db45b29cc06f7482ea56e9b20d3`.
- jvn65 container: `containerd://113c623b1bd453582781865c37b6ddc70f48437ef3bdbcaccebce40d3c011bfe`.
- lhr4x container: `containerd://49924036f12a366dba8d947d8dbeb38dd12b42bbaba62a73f4a6a7258b440ac6`.

## Gates

All local gates passed after replacing bootstrap RBAC/Job with a plain kind-only
synthetic Secret and pinning Express 4.22.3 / Redis client 4.7.1 exactly.
The final image upgrades Debian packages and removes npm/corepack after install
to eliminate fixed CRITICAL findings in the approved base image's build tooling.

```text
Unit test target: tests 7, pass 7, fail 0
Production image: naming to .../bank-notify-svc:local done; DONE 0.4s
Dockerfile policy: 4 tests, 4 passed, 0 warnings, 0 failures, 0 exceptions
Manifest policy: 33 tests, 33 passed, 0 warnings, 0 failures, 0 exceptions
Kind: STATUS: deployed
smoke GET /health -> 200 (want 200)
smoke GET /outbox/HG000000000 -> 200 (want 200)
Kind result: stage=smoke status=pass detail="all smoke paths answered"
Trivy: zero matching CRITICAL vulnerabilities; no secret findings (exit 0)
Parity helper tests: Ran 2 tests in 0.002s; OK
Compare: PASS: 52 FAIL: 0
```

Full local gate logs: `/home/ubuntu/notify-test-build.log`,
`/home/ubuntu/notify-build.log`, `/home/ubuntu/notify-policy.log`,
`/home/ubuntu/notify-kind.log`, `/home/ubuntu/notify-trivy.log`.
The kind-only fixture credential is deliberately explicit in the deps Secret
and `kind-secrets.env`; it is not a production credential or part of the image.
