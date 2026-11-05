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

The pinned verifier applies all kind-deps manifests into deps and waits for
its Deployments before importing kind-secrets.env into app-notify-svc only.
It supports no dependency secret source or ordering hook. The kind-only
fixture-secret.yaml therefore supplies the deps Secret with the same synthetic
password as kind-secrets.env. No manual secret bootstrap is required.

The fixture Secret is labelled synthetic/kind-only. Never use these fixtures
outside local kind. The pinned conftest gate renders only the application
chart; kind-deps is not part of that render. Its SECRET-02 rule prohibits
literal Secrets in platform manifests; this fixture is only for the local
dependency namespace, which is not labelled for platform admission enforcement.
The kind override disables ingress NetworkPolicy for local port-forward smoke.

The pinned smoke runner only supports GET, so platform.yaml checks /health.
Exercise POST /notify separately with the wave smoke request. For parity,
clear both independent Redis stores before replaying the harness; smoke
requests mutate rate counters and outboxes. Keep the legacy VM running.
