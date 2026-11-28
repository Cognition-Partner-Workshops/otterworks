# Fleet readiness runners

Install dependencies with `python -m pip install -r platform/standards/fleet/requirements.txt`.
Run the commands from `platform/standards/fleet`.

```sh
python fleet.py board inventory.json --markdown board.md
python fleet.py drift desired.yaml --observed snapshot.json --namespace dev --json drift.json --markdown drift.md
python fleet.py drift desired.yaml --context kind-dev --namespace dev --json drift.json --markdown drift.md
python fleet.py api rendered.yaml --target 1.35 --json api.json --markdown api.md
python -m unittest discover -p 'test_*.py'
```

The board accepts an object with a `workloads` array. Each row uses the keys in
`BOARD_FIELDS` in `fleet.py`. Status is `ready`, `held` or `rejected`.
A ready row requires every field. The renderer never changes a supplied status.

Drift compares declared fields, ignoring server defaults added to maps and changes
under `status`. Named lists such as containers compare by member name. File mode
also detects extra resources in the supplied snapshot. Live mode fetches only the
resources named in the desired file. Scope both inputs to the same resources in
one namespace. Do not include Secrets or confidential data in inputs or reports.

The API check accepts YAML streams, JSON objects and Kubernetes Lists. The
catalog covers built-in resource versions in the linked deprecation guide and
Endpoints deprecation in 1.33. Removed versions stay removed in subsequent minor
releases. A resource with no catalog finding still needs server-side validation for
fields, CRDs and admission policy.

Port-forward the deployment to a loopback address before sending load. Capture each
phase with the same JSON profile, context, namespace, deployment and URL. The
profile fields are `requests`, `rate_per_second`, `concurrency`, `timeout_seconds`,
`sample_seconds`, `p95_limit_ms` and `allowed_failures`.

```sh
python load_compare.py capture --profile profile.json --context kind-dev --namespace dev --deployment worker --url http://127.0.0.1:8080/work --json before.json --markdown before.md
python load_compare.py capture --profile profile.json --context kind-dev --namespace dev --deployment worker --url http://127.0.0.1:8080/work --json after.json --markdown after.md
python load_compare.py compare before.json after.json --json comparison.json --markdown comparison.md
```

Kubelet statistics require read access to the node stats endpoint via the API
server. Peak CPU uses the available kubelet samples. Latency
measures response headers for successful requests; failures have a separate
count. Restart totals refer to visible pods at each sample. With deployment
port-forward, the requests reach one pod even if the deployment has more replicas.

The commands return 0 for a completed clear check, 1 for drift, removed APIs or
a failed load gate, and 2 for input or tool errors. Deprecations alone do not fail
the version check. The load comparison returns the after gate and preserves both
phases in the report.
