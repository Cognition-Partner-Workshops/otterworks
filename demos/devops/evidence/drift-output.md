# Fleet drift — recorded kind Deployments

Observed: `kind-devops-20261128-1-34` (fixture: recorded, not live AWS).

Result: **RED** — 6 deployments checked, 3 differences.

| resource | field | state | desired | observed |
| --- | --- | --- | --- | --- |
| apps/Deployment/devops-fleet/collab-service | /metadata/labels/owner | missing | collaboration | unknown |
| apps/Deployment/devops-fleet/collab-service | /spec/template/metadata/labels/owner | missing | collaboration | unknown |
| apps/Deployment/devops-fleet/collab-service | /spec/template/spec/containers/collab-service/resources/requests | changed | {"cpu": "100m", "memory": "128Mi"} | {"cpu": "320m", "memory": "128Mi"} |
