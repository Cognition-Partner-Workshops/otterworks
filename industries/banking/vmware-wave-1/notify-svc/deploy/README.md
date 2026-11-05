# Local platform runtime

Node 20 runs one process per pod. PORT defaults to 3000; REDIS_URL defaults
to the legacy loopback address. REDIS_PASSWORD is supplied separately from
a Kubernetes Secret; credentials in REDIS_URL are rejected. Health requires
Redis PONG within one second. No runtime file writes are required.

All replicas share a single Redis for rate counters and outboxes. The kind
dependency is deliberately ephemeral (emptyDir, no persistence). Durability,
HA and retention remain undecided. Redis is not in the pinned approved base
image list; its official digest in kind-deps needs a platform-owned decision
before any shared-platform deployment. Owner banking-platform and cost center
bank-wave1 are local labels, not an assertion of an approved ownership mapping.

The pinned kind verifier installs dependencies before creating application
Secrets, and Secrets cannot cross namespaces. Before running it, create the
deps namespace in the isolated kind cluster and populate notify-redis there
from the same fixture file used for the application Secret:

```sh
kubectl create namespace deps
sed 's/^notify-redis\.//' deploy/kind-secrets.env |
  kubectl create secret generic notify-redis -n deps --from-env-file=/dev/stdin
```

Only deploy/kind-secrets.env contains the synthetic local password. Never use
this fixture outside local kind. The verifier imports it into app-notify-svc.
The kind override disables ingress NetworkPolicy for local port-forward smoke.

The pinned smoke runner only supports GET, so platform.yaml checks /health.
Exercise POST /notify separately with the wave smoke request. For parity,
clear both independent Redis stores before replaying the harness; smoke
requests mutate rate counters and outboxes. Keep the legacy VM running.
