# Fleet readiness board

## Desired versus observed drift (criterion 5)

**RED / HELD.** The comparison uses the recorded kind snapshot in
`devops-fleet`, not live AWS. Live `otterworks-dev` did not have this
namespace. A match below covers only requests, limits, Deployment spec replicas,
image, and owner labels; it does not make a workload upgrade-ready.
[Commands, scope and recommendations](drift.md) · [Linux output](drift-output.md) · [Windows output](drift-windows-output.md)

| Workload | Desired owner (observed, if different) | Last known-good Git SHA | Helm revision | Restart constraint | Drift / disposition |
| --- | --- | --- | --- | --- | --- |
| api-gateway | platform-edge | `74421355a6b2df82b2f3d984ffdfdfffa9c8aac2` | 1 | Missing | Checked fields match; rollout stays RED: observed Helm rev 2 is not ready. Separate recovery PR in flight. |
| auth-service | identity | `74421355a6b2df82b2f3d984ffdfdfffa9c8aac2` | 1 | Missing | Match |
| collab-service | collaboration (observed owner missing) | `74421355a6b2df82b2f3d984ffdfdfffa9c8aac2` | 1 | Missing | RED / HELD: CPU request `100m` → `320m`; owner labels missing from Deployment and pod template. |
| document-service | content | `74421355a6b2df82b2f3d984ffdfdfffa9c8aac2` | 1 | Restart only in an approved maintenance window; PDB `minAvailable: 2`. | Match |
| file-service | storage | `74421355a6b2df82b2f3d984ffdfdfffa9c8aac2` | 1 | Missing | Match |
| search-service | search | `74421355a6b2df82b2f3d984ffdfdfffa9c8aac2` | 1 | Missing | Match |

Windows rerun: exit 1, RED, same three collab-service differences as Linux (identical report). [Windows output](drift-windows-output.md)
