# Fleet readiness board

## Capacity envelope under bounded load (criterion 6)

**RED.** Local kind 1.34 (`kind-devops-20261128-1-34`, dev only), namespace `devops-fleet`. Each workload got the same `fixtures/load-profile.json` twice (before / after, 30 s apart, no change to the cluster between). Envelope = CPU peak within requests.cpu x replicas, no restarts, all replicas ready, replicas/HPA unchanged, p95 <= 200 ms and 0 failures. No recorded AWS data used.
[Commands, envelope table and records](load-comparison.md) · [Per-phase output](load/)

| Workload | Owner (desired) | p95 ms before / after | CPU peak m before / after (envelope) | Restarts / ready | Capacity |
| --- | --- | --- | --- | --- | --- |
| api-gateway | platform-edge | 20.6 / 17.7 | 27.3 / 53.3 (100) | 1 restart during load; 1 of 2 ready | **RED**: Helm rev 2 (`/healthz`) never ready; recovery PR in flight |
| auth-service | identity | 23.4 / 18.1 | 24.3 / 14.9 (100) | 0; 1 of 1 | Inside envelope |
| collab-service | collaboration (observed owner missing) | 20.5 / 27.1 | 17.0 / 14.7 (320 observed, 100 desired) | 0; 1 of 1 | Inside envelope; HELD for owner (no owner label, request drift) |
| document-service | content | 21.6 / 20.0 | 8.4 / 24.6 (200) | 0; 2 of 2 | Inside envelope |
| file-service | storage | 19.3 / 18.1 | 16.3 / 35.3 (100) | 0; 1 of 1 | Inside envelope |
| search-service | search | 2300.5 / 1899.8 | 24.8 / 25.0 (20, limit 25) | 0; 1 of 1 | **RED**: p95 9-11x limit, CPU above request at limit, HPA max 1 |
