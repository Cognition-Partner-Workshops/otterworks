# Looker connection

Create connection `sfx_fin` with the **Snowflake** dialect.
Database: `SFX_D1110_AFTER`; schema: `COMPAT`;
warehouse: `SFX_D1110_PARITY_WH`; timezone: `UTC`.
Authenticate the run's service user using key-pair (JWT) authentication.
Account, user, role and private key come from the platform secret manager;
no passwords or secret values belong here. svc_bi_semantic is retired.
Additional parameter: query_tag = {"run":"sfx-d1110","act":"consumers","consumer":"bi-semantic"}.

Enable PDTs with a separate writable scratch schema provisioned by the platform
team, not by this repo. Source schemas are read-only.
Create string user attribute `finance_warehouse_enabled` with default value
`yes` (default-on); set it to `no` to remove finance explore access.
Looker evaluates the four-hour datagroup trigger on its regenerator cadence.
