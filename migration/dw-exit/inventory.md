# Inventory

As of 2026-11-10; DBQL window 2026-08-12 through 2026-11-09 inclusive.

```json
{
  "by_kind": {
    "bteq": 25,
    "catalog": 6,
    "fastload": 22,
    "macro": 6,
    "mapping": 20,
    "procedure": 4,
    "session": 20,
    "table": 84,
    "tpt": 20,
    "view": 11,
    "workflow": 3,
    "worklet": 1
  },
  "total": 222,
  "loc_total": 5919,
  "complexity": {
    "medium": 160,
    "low": 49,
    "high": 13
  },
  "dead": [
    "SFX_AUDIT.AUDIT_EVENT_ARCHIVE",
    "SFX_AUDIT.M_ARCHIVE_OVERVIEW",
    "SFX_DOCUMENTS.SEARCH_INDEX_LOG",
    "SFX_DOCUMENTS.V_SEARCH_HISTORY",
    "SFX_USERS.USER_PREF",
    "SFX_USERS.V_USER_SETTINGS"
  ],
  "setup_only_reads_not_dead": [
    "DBC.DBC_QRYLOG",
    "DBC.DBC_QRYLOGOBJECTS",
    "DBC.DBC_TABLESV",
    "DBC.QRYLOGOBJECTSV",
    "DBC.QRYLOGV",
    "DBC.TABLESV",
    "SFX_AUDIT.STG_AUDIT_EVENT_ARCHIVE",
    "SFX_AUDIT.V_CUSTOMER_RECON",
    "SFX_BILLING.V_SUBSCRIPTION_PLANS",
    "SFX_DOCUMENTS.STG_SEARCH_INDEX_LOG"
  ],
  "not_in_warehouse_etl": [
    "FIN_ANALYST_JMORALES",
    "nb_dsci_pkhan",
    "svc_admin_fin",
    "svc_analytics_dash",
    "svc_bi_semantic",
    "svc_billing_export",
    "svc_etl_audit",
    "svc_etl_billing",
    "svc_etl_docs",
    "svc_etl_users",
    "svc_legacy_billing",
    "svc_partner_sftp",
    "svc_report_recon"
  ],
  "not_in_any_repo_code": [
    "FIN_ANALYST_JMORALES",
    "nb_dsci_pkhan",
    "svc_etl_audit",
    "svc_etl_billing",
    "svc_etl_docs",
    "svc_etl_users"
  ],
  "waves": {
    "1": {
      "total": 108,
      "by_kind": {
        "catalog": 6,
        "fastload": 22,
        "macro": 1,
        "mapping": 6,
        "session": 6,
        "table": 45,
        "tpt": 20,
        "view": 2
      },
      "by_target": {
        "dbt_model": 49,
        "retire": 20,
        "snowflake_scripting": 39
      }
    },
    "2": {
      "total": 51,
      "by_kind": {
        "bteq": 12,
        "mapping": 9,
        "session": 9,
        "table": 21
      },
      "by_target": {
        "dbt_model": 35,
        "snowflake_scripting": 12,
        "snowpark": 4
      }
    },
    "3": {
      "total": 52,
      "by_kind": {
        "bteq": 13,
        "macro": 5,
        "mapping": 5,
        "procedure": 4,
        "session": 5,
        "table": 18,
        "workflow": 1,
        "worklet": 1
      },
      "by_target": {
        "dbt_model": 25,
        "snowflake_scripting": 24,
        "snowpark": 3
      }
    },
    "4": {
      "total": 11,
      "by_kind": {
        "view": 9,
        "workflow": 2
      },
      "by_target": {
        "compatibility_view": 9,
        "snowflake_scripting": 2
      }
    }
  },
  "licence_counters": {
    "teradata_objects": {
      "remaining": 111,
      "target": 0
    },
    "powercenter_mappings": {
      "remaining": 20,
      "target": 0
    },
    "spark_executor_hours": {
      "remaining": 0,
      "target": 0,
      "status": "no Spark estate on branch yet"
    },
    "powercenter_annual_cost": {
      "value": 412000,
      "currency": "USD"
    }
  },
  "dead_dependents": [
    "SFX_AUDIT.STG_AUDIT_EVENT_ARCHIVE",
    "SFX_DOCUMENTS.STG_SEARCH_INDEX_LOG",
    "SFX_USERS.STG_USER_PREF",
    "audit_audit_event_archive",
    "documents_search_index_log",
    "m_SFX_AUDIT_EVENT_ARCHIVE",
    "s_m_SFX_AUDIT_EVENT_ARCHIVE",
    "users_user_pref"
  ]
}
```

0 Spark jobs found. `etl/spark` absent. `migration/job/ldm/engines/spark_load.py` is a separate legacy demo, excluded.

Scan evidence for every DBQL reader (tracked repository text, excluding DBQL, tests and generated assessment):

```json
{
  "FIN_ANALYST_JMORALES": {
    "warehouse_etl_hits": [],
    "repo_hits": []
  },
  "nb_dsci_pkhan": {
    "warehouse_etl_hits": [],
    "repo_hits": []
  },
  "svc_admin_fin": {
    "warehouse_etl_hits": [],
    "repo_hits": [
      "consumers/registry.yaml",
      "services/admin-service/README.md",
      "services/admin-service/config/finance_warehouse.yml"
    ]
  },
  "svc_analytics_dash": {
    "warehouse_etl_hits": [],
    "repo_hits": [
      "consumers/registry.yaml",
      "services/analytics-service/README.md",
      "services/analytics-service/src/main/resources/com/otterworks/analytics/finance/teradata.conf"
    ]
  },
  "svc_bi_semantic": {
    "warehouse_etl_hits": [],
    "repo_hits": [
      "consumers/bi/README.md",
      "consumers/bi/connection.md",
      "consumers/registry.yaml"
    ]
  },
  "svc_billing_export": {
    "warehouse_etl_hits": [],
    "repo_hits": [
      "consumers/registry.yaml",
      "services/billing-service/README.md",
      "services/billing-service/app/warehouse/config.toml"
    ]
  },
  "svc_etl_audit": {
    "warehouse_etl_hits": [],
    "repo_hits": []
  },
  "svc_etl_billing": {
    "warehouse_etl_hits": [],
    "repo_hits": []
  },
  "svc_etl_docs": {
    "warehouse_etl_hits": [],
    "repo_hits": []
  },
  "svc_etl_users": {
    "warehouse_etl_hits": [],
    "repo_hits": []
  },
  "svc_legacy_billing": {
    "warehouse_etl_hits": [],
    "repo_hits": [
      "consumers/registry.yaml",
      "services/legacy-billing/README.md",
      "services/legacy-billing/app/finance_warehouse.ini"
    ]
  },
  "svc_partner_sftp": {
    "warehouse_etl_hits": [],
    "repo_hits": [
      "consumers/partner-extract/README.md",
      "consumers/partner-extract/sql/partner_invoice_extract.bteq",
      "consumers/registry.yaml"
    ]
  },
  "svc_report_recon": {
    "warehouse_etl_hits": [],
    "repo_hits": [
      "consumers/registry.yaml",
      "services/report-service/README.md",
      "services/report-service/src/main/resources/com/otterworks/report/financewarehouse/teradata.properties"
    ]
  }
}
```
