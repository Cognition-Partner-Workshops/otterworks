"""Non-destructive provisioning for the support lookup identity."""

from __future__ import annotations

import sf_attribution as sf

EP = sf.endpoint("cs_doc_usage_dashboard_support_lookup")
ROLE = "ROLE_CS_DOC_USAGE_DASHBOARD_SUPPORT_LOOKUP"


def provision_sql(public_key=None, *, user_exists=False):
    if not public_key and not user_exists:
        raise ValueError("SNOWFLAKE_EXT_SUPPORT_PUBLIC_KEY required to create the support service user")
    comment = sf.sql_string(sf.external_comment(workload=EP.workload, csid=EP.csid))
    statements = [
        f"CREATE ROLE IF NOT EXISTS {ROLE} COMMENT = {comment}",
        f"GRANT USAGE ON DATABASE {EP.database} TO ROLE {ROLE}",
        f"GRANT USAGE ON WAREHOUSE {EP.warehouse} TO ROLE {ROLE}",
    ]
    if not user_exists:
        statements.append(sf.service_user_ddl(EP, rsa_public_key=public_key, role=ROLE)
                          + " DEFAULT_SECONDARY_ROLES = ()")
    statements.append(f"GRANT ROLE {ROLE} TO USER {EP.service_user}")
    return statements
