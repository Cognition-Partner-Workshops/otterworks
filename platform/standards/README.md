# Platform standards

The platform team owns this folder and its rules: an application is ready for the shared cluster when its pull request passes the pipeline template in `.github/workflows/platform-app-pipeline.yml` against a commit of this folder, and nothing reaches the cluster any other way.

## Application requirements

- A `Dockerfile` whose stages start from an image in `base-images.yaml`, written with the exact digest. The first stage is named `test` and runs the unit tests, so `docker build --target test` is the unit test step on every runtime.
- A final stage that sets `USER` to a numeric uid other than 0 and bakes in no credential.
- Configuration from environment variables and mounted files. Secrets arrive as references: `secretEnv` in the chart values points at a Kubernetes Secret that External Secrets fills from AWS Secrets Manager, and the image, the chart and every ConfigMap carry only the reference.
- Logs on stdout and stderr. Nothing writes a log file inside the container.
- A `/health` endpoint that answers 200 when the service can take traffic. The chart wires it to both probes.
- A `deploy/` folder with `values.yaml` for the chart in `helm/app` (with `app`, `owner` and `costCenter` set) and `platform.yaml` with the smoke paths the pipeline calls. Optional files are `values-ci.yaml` (overrides for the kind cluster), `kind-deps/` (throwaway dependencies such as a database for the kind run) and `kind-secrets.env` (test-only values the kind run loads as Secrets).

## Rules the gate checks

| Id | Rule |
|---|---|
| BASE-01 | Every `FROM` is an approved image pinned by digest |
| BASE-02 | The final stage runs as a numeric non-root user |
| SECRET-01 to SECRET-04 | No credential as a literal in env, Secret manifests, ConfigMaps, `ENV` or `ARG` |
| SEC-01, SEC-02 | Containers run as non-root on a read-only root filesystem (writable paths are `emptyDir` mounts) |
| RES-01 | CPU and memory requests and limits are set, inside the namespace limit range of 500m and 256Mi by default |
| PROBE-01 | Long-running services have liveness and readiness probes |
| LABEL-01 | Workloads carry `app`, `owner` and `cost-center` |
| REG-01, REG-02 | Images come from the approved ECR registry with an immutable tag |
| NET-01 | Services are ClusterIP behind the shared ingress-nginx |

conftest checks the Dockerfile and the rendered chart in the pipeline (`policy/conftest`), Kyverno enforces the same manifest rules at admission (`policy/kyverno`), and Trivy adds secret rules for passwords in settings files and database URLs (`policy/trivy`). A pull request that breaks a rule fails the gate, and the runtime stage does not start.

## Pipeline stages

Unit tests, container build, Trivy image and secret scan, Syft SBOM, the policy gate, then a kind cluster on the runner with Kyverno enforcing, a Helm install and the smoke paths. The run uploads the scan, the SBOM, the policy output and the pod logs and events as one artifact, and posts a results table on the pull request. With `eks_deploy: true` and the repository variable `BANK_W1_EKS` set, the image goes to ECR and the chart to an ephemeral namespace on `otterworks-dev`, deployed by the pipeline's OIDC role.

## Changing the standard

Bump a digest or a rule through a pull request to `main`. `scripts/selftest.sh` must still pass the sample service and fail each broken rule, and the `platform-standards` workflow runs the template end to end on `examples/sample-service`. Applications move to the new standard by updating the commit they pin.

## Local use

```bash
platform/standards/scripts/policy-check.sh <app-dir> 599083837640.dkr.ecr.us-east-1.amazonaws.com/otterworks/<name> <tag>
platform/standards/scripts/kind-verify.sh  <app-dir> 599083837640.dkr.ecr.us-east-1.amazonaws.com/otterworks/<name> <tag>
```
