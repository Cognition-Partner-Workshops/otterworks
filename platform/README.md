# OtterWorks platform ownership

The internal developer platform lives in this monorepo. Platform Engineering owns the reusable path to build, deploy, and operate a service. Service teams own what their services do and how they behave in production. A shared directory does not make the contents platform-owned.

| Area | Platform Engineering owns | Service teams own |
| --- | --- | --- |
| Runtime and tenancy | [VPC, EKS, and ECR](terraform/), shared ingress, tenant isolation and lifecycle, quotas, and the registry and identity mechanisms. | Service capacity needs, dependency declarations, and least-privilege access requirements. |
| Build and deployment | The [delivery catalog](delivery/services.json), tenant and release workflows, approved base images, [reusable CI and Helm standards](standards/), and how secrets reach workloads. | Dockerfile and application tests, deploy values, health and smoke endpoints, and service-specific config. |
| Data and messaging | Reusable provisioning and operations for shared backing services, backups, and credential delivery. Keep the [current Terraform state boundaries](../infrastructure/terraform/) until a state-safe migration is planned. | Data models, migrations, retention requirements, event semantics, and which services need access. |
| Observability and response | Telemetry collection and transport, shared dashboards, cluster alerts, and platform incident response. | Instrumentation, service dashboards and SLOs, service runbooks, and response to application incidents. |
| APIs and events | Compatibility tooling and common conventions, not domain schemas. | Producers own their APIs and events, including specs in [shared/](../shared/); consumers review compatibility changes. Gateway route behavior stays with the relevant service and gateway maintainers. |

## Legacy delivery: register once

[The delivery catalog](delivery/services.json) is the inventory for the golden app: tenant change detection and builds, release builds, and the standalone and tenant deploy scripts read it. Each entry names the Helm release and build context. The optional `port` preserves the backend's internal service port, `core` opts into the small tenant profile, and `jvm` selects the existing JVM memory override. The default `full` profile still includes every registered app. A catalog edit rebuilds the full image set on the next eligible tenant delivery run so a new entry gets an image even if its source did not change.

For a service joining this delivery path, its team supplies the Dockerfile, chart or values, and service wiring. Platform reviews the catalog entry and has the ECR repository ready before the first publishing run. Catalog registration doesn't provision cloud resources, set up routes or data access, or add the local Compose service. Registry lifecycle is separate: removing a deployment entry must not delete its images.

Run `bash platform/delivery/check.sh` to check the inventory and build selection before review.

## New services: start with the standard

1. Use the [sample service](standards/examples/sample-service/) as a reference for the test stage, health endpoint, and service-owned deploy values.
2. Call the [reusable verification workflow](../.github/workflows/platform-app-pipeline.yml) from the monorepo, pointing it at the application's directory and using the same standards commit as the caller. Run it without EKS deployment first; it builds and smoke-tests in kind. This is not the legacy tenant release workflow.
3. Pilot the shared chart on one existing stateless service in an isolated tenant before switching golden delivery. Compare rendered names and selectors, ports, config and secret references, probes, and network policy; run the service's contract and smoke tests. Leave existing charts in place until each migration passes.
4. Move shared infrastructure modules and baseline telemetry under platform stewardship incrementally. Assign GitHub review rules once the team slugs are confirmed; require both the affected service team and Platform Engineering for delivery contract changes.
