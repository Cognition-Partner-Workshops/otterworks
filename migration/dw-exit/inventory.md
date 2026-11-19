# Inventory

DBQL window 2026-08-12 through 2026-11-09 inclusive.

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
    "spark_job": 30,
    "table": 84,
    "tpt": 20,
    "view": 11,
    "workflow": 3,
    "worklet": 1
  },
  "total": 252,
  "loc_total": 6395,
  "complexity": {
    "medium": 181,
    "low": 58,
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
      "total": 111,
      "by_kind": {
        "catalog": 6,
        "fastload": 22,
        "macro": 1,
        "mapping": 6,
        "session": 6,
        "spark_job": 3,
        "table": 45,
        "tpt": 20,
        "view": 2
      },
      "by_target": {
        "dbt_model": 49,
        "retire": 23,
        "snowflake_scripting": 39
      }
    },
    "2": {
      "total": 72,
      "by_kind": {
        "bteq": 12,
        "mapping": 9,
        "session": 9,
        "spark_job": 21,
        "table": 21
      },
      "by_target": {
        "dbt_model": 42,
        "snowflake_scripting": 12,
        "snowpark": 18
      }
    },
    "3": {
      "total": 58,
      "by_kind": {
        "bteq": 13,
        "macro": 5,
        "mapping": 5,
        "procedure": 4,
        "session": 5,
        "spark_job": 6,
        "table": 18,
        "workflow": 1,
        "worklet": 1
      },
      "by_target": {
        "dbt_model": 30,
        "snowflake_scripting": 24,
        "snowpark": 4
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
      "remaining": 178,
      "target": 0
    },
    "powercenter_mappings": {
      "remaining": 20,
      "target": 0
    },
    "spark_executor_hours": {
      "remaining": 0.206092502,
      "in_window": 0.198646669,
      "target": 0,
      "scope": "all packaged eventlogs; in_window reported separately"
    },
    "powercenter_annual_cost": {
      "value": 412000,
      "currency": "USD"
    },
    "powercenter_objects": {
      "remaining": 44,
      "target": 0
    },
    "spark_jobs": {
      "remaining": 27,
      "target": 0
    },
    "licence_dependencies": {
      "remaining": 252,
      "total": 252,
      "target": 0
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
  ],
  "stale": [
    {
      "id": "n21635c3e4ef179d8",
      "name": "SFX_AUDIT.V_CUSTOMER_RECON",
      "review": "owner review; not auto-retired",
      "window": [
        "2026-08-12",
        "2026-11-09"
      ],
      "usage_counts": {
        "READ": 1,
        "WRITE": 0
      },
      "read_count": 1,
      "last_read": "2026-08-12 06:07:11",
      "last_write": null,
      "recent_accesses": [
        {
          "QueryID": "111000000069",
          "principal": "svc_report_recon",
          "timestamp": "2026-08-12 06:07:11",
          "usage_type": "READ"
        }
      ]
    },
    {
      "id": "n21655cefa5f6f219",
      "name": "SFX_BILLING.V_SUBSCRIPTION_PLANS",
      "review": "owner review; not auto-retired",
      "window": [
        "2026-08-12",
        "2026-11-09"
      ],
      "usage_counts": {
        "READ": 1,
        "WRITE": 0
      },
      "read_count": 1,
      "last_read": "2026-08-12 06:08:36",
      "last_write": null,
      "recent_accesses": [
        {
          "QueryID": "111000000070",
          "principal": "svc_report_recon",
          "timestamp": "2026-08-12 06:08:36",
          "usage_type": "READ"
        }
      ]
    }
  ]
}
```

30 Spark jobs linked to merged sources on demo-snowflake-dw-exit.

Scan evidence for every DBQL reader:

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
