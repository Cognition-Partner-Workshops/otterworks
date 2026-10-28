"""Column map shared by extract_state.py and load_state.py (run databricks-1793146609, batch w1-b02).

The fourteen ow_tp_invoicing tables in FK order: parents before children so a single
TRUNCATE of all fourteen and a sequential COPY satisfies referential integrity at load
time. Target schema is ow_tp_invoicing on Lakebase project ow-tp-billing, branch
mig-invoicing-w1, database ow_tp.
"""
from __future__ import annotations

SOURCE_SCHEMA = "OW_BILLING"
TARGET_SCHEMA = "ow_tp_invoicing"
TARGET_DATABASE = "ow_tp"

TABLES: list[tuple[str, str, list[tuple[str, str]]]] = [
    ("CODES", "codes", [("CODE_TYPE", "code_type"), ("CODE_VAL", "code_val"),
                        ("CODE_DESC", "code_desc")]),
    ("TENANTS", "tenants", [("ID", "id"), ("NAME", "name"),
                            ("TAX_EXEMPT_YN", "tax_exempt_yn"), ("STATUS_CD", "status_cd")]),
    ("PLANS", "plans", [("ID", "id"), ("CODE", "code"), ("TIER_CD", "tier_cd"),
                        ("MONTHLY_FEE", "monthly_fee"), ("INCLUDED_UNITS", "included_units"),
                        ("OVERAGE_RATE", "overage_rate"), ("ACTIVE_YN", "active_yn")]),
    ("SUBSCRIPTIONS", "subscriptions", [("ID", "id"), ("TENANT_ID", "tenant_id"), ("PLAN_ID", "plan_id"),
                                        ("STARTS_ON", "starts_on"), ("ENDS_ON", "ends_on"),
                                        ("STATUS_CD", "status_cd"), ("SUSPENDED_ON", "suspended_on")]),
    ("SUBSCRIPTIONS_HIST", "subscriptions_hist", [("HIST_ID", "hist_id"), ("HIST_DT", "hist_dt"),
                                                  ("HIST_OP", "hist_op"), ("ID", "id"), ("TENANT_ID", "tenant_id"),
                                                  ("PLAN_ID", "plan_id"), ("STARTS_ON", "starts_on"),
                                                  ("ENDS_ON", "ends_on"), ("STATUS_CD", "status_cd"),
                                                  ("SUSPENDED_ON", "suspended_on")]),
    ("USAGE_EVENTS", "usage_events", [("ID", "id"), ("TENANT_ID", "tenant_id"),
                                      ("OCCURRED_AT", "occurred_at"), ("UNITS", "units"),
                                      ("KIND_CD", "kind_cd")]),
    ("RATING_PERIODS", "rating_periods", [("ID", "id"), ("TENANT_ID", "tenant_id"),
                                          ("PERIOD_START", "period_start"), ("PERIOD_END", "period_end")]),
    ("RATING_RESULTS", "rating_results", [("ID", "id"), ("PERIOD_ID", "period_id"),
                                          ("SUBSCRIPTION_ID", "subscription_id"), ("USED_UNITS", "used_units"),
                                          ("QUOTA_UNITS", "quota_units"), ("ROLLOVER_UNITS", "rollover_units"),
                                          ("BILLABLE_UNITS", "billable_units"), ("OVERAGE_AMOUNT", "overage_amount"),
                                          ("CREATED_AT", "created_at")]),
    ("INVOICES", "invoices", [("ID", "id"), ("TENANT_ID", "tenant_id"), ("PERIOD_ID", "period_id"),
                              ("ISSUED_AT", "issued_at"), ("SUBTOTAL", "subtotal"), ("TAX", "tax"),
                              ("TOTAL", "total"), ("STATUS_CD", "status_cd")]),
    ("INVOICE_LINES", "invoice_lines", [("ID", "id"), ("INVOICE_ID", "invoice_id"), ("LINE_NO", "line_no"),
                                        ("LINE_TYPE", "line_type"), ("DESCRIPTION", "description"),
                                        ("AMOUNT", "amount")]),
    ("CREDIT_NOTES", "credit_notes", [("ID", "id"), ("TENANT_ID", "tenant_id"), ("ISSUED_ON", "issued_on"),
                                      ("AMOUNT", "amount"), ("REMAINING_AMOUNT", "remaining_amount")]),
    ("DUNNING_ATTEMPTS", "dunning_attempts", [("ID", "id"), ("TENANT_ID", "tenant_id"),
                                              ("INVOICE_ID", "invoice_id"), ("ATTEMPT_NO", "attempt_no"),
                                              ("SCHEDULED_FOR", "scheduled_for"), ("STATUS_CD", "status_cd")]),
    ("NOTIFICATIONS", "notifications", [("ID", "id"), ("TENANT_ID", "tenant_id"),
                                        ("KIND_CD", "kind_cd"), ("SENT_AT", "sent_at")]),
    ("BILLING_AUDIT_LOG", "billing_audit_log", [("LOG_ID", "log_id"), ("LOGGED_AT", "logged_at"),
                                                  ("MODULE", "module"), ("MESSAGE", "message")]),
]
CHAR1_COLUMNS: set[str] = {"tax_exempt_yn", "active_yn"}
