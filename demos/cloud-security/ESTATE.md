# Cloud security fixture estate

| Area | Fixture inputs | Boundary |
| --- | --- | --- |
| IAM | Terraform plan-shaped JSON and an approved action/resource scope | Offline only. The role and bucket identifiers are synthetic. |
| Image | Document-service build, approved base digest, wheel hash, and pinned Trivy database | A local image delta against the repository scanner configuration; unrelated findings are not part of the delta. |
| Database | Disposable Postgres with two ordinary login roles and a separate schema owner | Ten synthetic rows per tenant. The database is published to loopback only and stores its data in tmpfs. |
| Network | Rendered Kubernetes policies, test pods, and an expected TCP matrix | Pod-to-pod in a local kind namespace with NetworkPolicy enforcement. No external services or load balancers. |
| Evidence | Control evidence schema, owners, and exception records | The ledger is generated from run results; no run results are stored here. |
