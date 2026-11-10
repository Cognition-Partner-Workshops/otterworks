# Looker connection
Create connection `tdprod_fin` using the **Teradata** dialect, host
`tdprod-fin.otterworks.internal`, database `SFX_BILLING`, user `svc_bi_semantic`,
password `not-a-real-password`. These are fake lab credentials. <!-- gitleaks:allow -->
Enable PDTs and configure a writable scratch schema separate from SFX_BILLING.
Create string user attribute `finance_warehouse_enabled` with default value
`yes` (default-on); set it to `no` to remove finance explore access.
Looker evaluates the four-hour datagroup trigger on its regenerator cadence.
