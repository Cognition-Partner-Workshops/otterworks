from dataclasses import dataclass


@dataclass(frozen=True)
class Column:
    name: str
    kind: str


@dataclass(frozen=True)
class Table:
    area: str
    name: str
    columns: tuple
    divisor: int = 1
    fixed: int = 0

    @property
    def database(self):
        return "SFX_" + self.area.upper()

    @property
    def names(self):
        return tuple(c.name for c in self.columns)

    @property
    def is_set(self):
        return self.name == "STORAGE_USAGE_DAILY"

    def count(self, rows):
        if self.name == 'GL_JOURNAL_LINE':
            return 4 * max(1, rows // 10) + 3 * max(1, rows // 200)
        return self.fixed or max(1, rows // self.divisor)


TABLES = (
    Table("billing", "CUSTOMER_ACCOUNT", (
        Column("CUSTOMER_ID", "B"),
        Column("OWNER_USER_ID", "B"),
        Column("ACCOUNT_NAME", "V100"),
        Column("STATUS_CD", "C12"),
        Column("CURRENCY_CD", "C3"),
        Column("CREATED_DT", "D"),
        Column("ACCOUNT_NUMBER", "V24"),
        Column("COUNTRY_CD", "C2"),
        Column("REGION_CD", "V20"),
    ), 10, 0),
    Table("billing", "PLAN_CATALOG", (
        Column("PLAN_ID", "B"),
        Column("PLAN_CODE", "C10"),
        Column("PLAN_NAME", "V80"),
        Column("MONTHLY_FEE", "N"),
        Column("CURRENCY_CD", "C3"),
    ), 0, 40),
    Table("billing", "SUBSCRIPTION", (
        Column("SUBSCRIPTION_ID", "B"),
        Column("CUSTOMER_ID", "B"),
        Column("PLAN_CODE", "V10"),
        Column("START_DT", "D"),
        Column("END_DT", "D"),
        Column("STATUS_CD", "C12"),
    ), 5, 0),
    Table("billing", "INVOICE_HDR", (
        Column("INVOICE_ID", "B"),
        Column("CUSTOMER_ID", "B"),
        Column("SUBSCRIPTION_ID", "B"),
        Column("INVOICE_DT", "D"),
        Column("BILL_DT", "D"),
        Column("PERIOD_START_DT", "D"),
        Column("CURRENCY_CD", "C3"),
        Column("TOTAL_AMOUNT", "N"),
        Column("INVOICE_NUMBER", "V32"),
        Column("TAX_RATE_ID", "B"),
        Column("SUBTOTAL_AMOUNT", "N"),
        Column("TAX_AMOUNT", "N"),
        Column("INVOICE_PERIOD", "C7"),
        Column("PERIOD_KEY", "I"),
        Column("PRIOR_PERIOD_END_DT", "D"),
        Column("INVOICE_MONTH", "I"),
        Column("PERIOD_CLOSED_CD", "C1"),
        Column("CURRENCY_CONTROL_TOTAL", "N"),
    ), 1, 0),
    Table("billing", "INVOICE_LINE", (
        Column("INVOICE_LINE_ID", "B"),
        Column("INVOICE_ID", "B"),
        Column("LINE_NO", "I"),
        Column("DESCRIPTION", "V120"),
        Column("QUANTITY", "I"),
        Column("UNIT_PRICE", "N"),
        Column("LINE_AMOUNT", "N"),
    ), 1, 0),
    Table("billing", "PAYMENT", (
        Column("PAYMENT_ID", "B"),
        Column("INVOICE_ID", "B"),
        Column("CUSTOMER_ID", "B"),
        Column("PAYMENT_DT", "D"),
        Column("AMOUNT", "N"),
        Column("METHOD_CD", "C12"),
        Column("PAYMENT_REFERENCE", "V32"),
    ), 1, 0),
    Table("billing", "CREDIT_NOTE", (
        Column("CREDIT_NOTE_ID", "B"),
        Column("INVOICE_ID", "B"),
        Column("CUSTOMER_ID", "B"),
        Column("CREDIT_DT", "D"),
        Column("AMOUNT", "N"),
        Column("REASON_CD", "C12"),
        Column("CREDIT_NUMBER", "V32"),
        Column("REASON_TEXT", "V120"),
    ), 20, 0),
    Table("billing", "TAX_RATE", (
        Column("TAX_RATE_ID", "B"),
        Column("COUNTRY_CD", "C2"),
        Column("REGION_CD", "V20"),
        Column("RATE", "Q"),
        Column("EFFECTIVE_DT", "D"),
    ), 0, 200),
    Table("billing", "USAGE_DAILY", (
        Column("USAGE_ID", "B"),
        Column("CUSTOMER_ID", "B"),
        Column("SUBSCRIPTION_ID", "B"),
        Column("USAGE_DT", "D"),
        Column("UNITS", "B"),
        Column("USAGE_TYPE", "C12"),
    ), 1, 0),
    Table("billing", "BILLING_ADJ", (
        Column("ADJUSTMENT_ID", "B"),
        Column("CUSTOMER_ID", "B"),
        Column("INVOICE_ID", "B"),
        Column("ADJUSTMENT_DT", "D"),
        Column("AMOUNT", "N"),
        Column("REASON_CD", "C12"),
    ), 20, 0),
    Table("documents", "FOLDER", (
        Column("FOLDER_ID", "B"),
        Column("OWNER_USER_ID", "B"),
        Column("CUSTOMER_ID", "B"),
        Column("FOLDER_NAME", "V100"),
        Column("CREATED_DT", "D"),
    ), 10, 0),
    Table("documents", "DOCUMENT", (
        Column("DOCUMENT_ID", "B"),
        Column("FOLDER_ID", "B"),
        Column("OWNER_USER_ID", "B"),
        Column("CUSTOMER_ID", "B"),
        Column("DOCUMENT_NAME", "V120"),
        Column("CREATED_DT", "D"),
        Column("STATUS_CD", "C12"),
        Column("FILE_TYPE", "C8"),
    ), 5, 0),
    Table("documents", "DOC_VERSION", (
        Column("VERSION_ID", "B"),
        Column("DOCUMENT_ID", "B"),
        Column("VERSION_NO", "I"),
        Column("VERSION_TS", "T"),
        Column("FILE_SIZE", "B"),
        Column("CONTENT_HASH", "V64"),
    ), 1, 0),
    Table("documents", "DOC_SHARE", (
        Column("SHARE_ID", "B"),
        Column("DOCUMENT_ID", "B"),
        Column("USER_ID", "B"),
        Column("ACCESS_LEVEL", "C12"),
        Column("SHARED_DT", "D"),
    ), 2, 0),
    Table("documents", "DOC_TAG", (
        Column("TAG_ID", "B"),
        Column("DOCUMENT_ID", "B"),
        Column("TAG_NAME", "V40"),
        Column("CREATED_DT", "D"),
    ), 2, 0),
    Table("documents", "FILE_OBJECT", (
        Column("FILE_OBJECT_ID", "B"),
        Column("DOCUMENT_ID", "B"),
        Column("OBJECT_KEY", "V160"),
        Column("BYTES_USED", "B"),
        Column("STORAGE_CLASS", "C12"),
        Column("CREATED_DT", "D"),
    ), 1, 0),
    Table("documents", "DOC_COMMENT", (
        Column("COMMENT_ID", "B"),
        Column("DOCUMENT_ID", "B"),
        Column("USER_ID", "B"),
        Column("COMMENT_TEXT", "V160"),
        Column("CREATED_TS", "T"),
    ), 1, 0),
    Table("documents", "COLLAB_SESSION", (
        Column("SESSION_ID", "B"),
        Column("DOCUMENT_ID", "B"),
        Column("USER_ID", "B"),
        Column("START_TS", "T"),
        Column("END_TS", "T"),
    ), 1, 0),
    Table("documents", "STORAGE_USAGE_DAILY", (
        Column("STORAGE_USAGE_ID", "B"),
        Column("CUSTOMER_ID", "B"),
        Column("OWNER_USER_ID", "B"),
        Column("USAGE_DT", "D"),
        Column("BYTES_USED", "B"),
        Column("OBJECT_COUNT", "I"),
    ), 1, 0),
    Table("documents", "SEARCH_INDEX_LOG", (
        Column("INDEX_LOG_ID", "B"),
        Column("DOCUMENT_ID", "B"),
        Column("INDEXED_TS", "T"),
        Column("STATUS_CD", "C12"),
        Column("TOKEN_COUNT", "I"),
    ), 1, 0),
    Table("users", "APP_USER", (
        Column("USER_ID", "B"),
        Column("DISPLAY_NAME", "V60"),
        Column("EMAIL", "V120"),
        Column("STATUS_CD", "C12"),
        Column("CREATED_DT", "D"),
    ), 10, 0),
    Table("users", "USER_PROFILE", (
        Column("PROFILE_ID", "B"),
        Column("USER_ID", "B"),
        Column("TITLE", "V60"),
        Column("COUNTRY_CD", "C2"),
        Column("TIMEZONE", "V40"),
    ), 10, 0),
    Table("users", "TEAM", (
        Column("TEAM_ID", "B"),
        Column("OWNER_USER_ID", "B"),
        Column("TEAM_NAME", "V80"),
        Column("CREATED_DT", "D"),
    ), 100, 0),
    Table("users", "TEAM_MEMBER", (
        Column("TEAM_MEMBER_ID", "B"),
        Column("TEAM_ID", "B"),
        Column("USER_ID", "B"),
        Column("ROLE_CD", "C12"),
        Column("JOINED_DT", "D"),
    ), 5, 0),
    Table("users", "ROLE_GRANT", (
        Column("GRANT_ID", "B"),
        Column("USER_ID", "B"),
        Column("ROLE_CD", "C12"),
        Column("GRANTED_DT", "D"),
    ), 10, 0),
    Table("users", "SSO_IDENTITY", (
        Column("IDENTITY_ID", "B"),
        Column("USER_ID", "B"),
        Column("PROVIDER_CD", "C12"),
        Column("SUBJECT_ID", "V100"),
        Column("CREATED_DT", "D"),
    ), 10, 0),
    Table("users", "LOGIN_EVENT", (
        Column("LOGIN_ID", "B"),
        Column("USER_ID", "B"),
        Column("LOGIN_TS", "T"),
        Column("RESULT_CD", "C12"),
        Column("CLIENT_TYPE", "C12"),
    ), 1, 0),
    Table("users", "USER_ACTIVITY_DAILY", (
        Column("ACTIVITY_ID", "B"),
        Column("USER_ID", "B"),
        Column("ACTIVITY_DT", "D"),
        Column("LOGIN_COUNT", "I"),
        Column("DOCUMENT_COUNT", "I"),
    ), 10, 0),
    Table("users", "USER_PREF", (
        Column("PREF_ID", "B"),
        Column("USER_ID", "B"),
        Column("PREF_NAME", "V40"),
        Column("PREF_VALUE", "V120"),
        Column("UPDATED_DT", "D"),
    ), 10, 0),
    Table("users", "USER_STATUS_HIST", (
        Column("STATUS_HISTORY_ID", "B"),
        Column("USER_ID", "B"),
        Column("STATUS_CD", "C12"),
        Column("VALID_FROM", "D"),
        Column("VALID_TO", "D"),
    ), 5, 0),
    Table("audit", "AUDIT_EVENT", (
        Column("EVENT_ID", "B"),
        Column("ACTOR_USER_ID", "B"),
        Column("DOCUMENT_ID", "B"),
        Column("CUSTOMER_ID", "B"),
        Column("EVENT_TS", "T"),
        Column("EVENT_TYPE", "C12"),
        Column("DETAILS", "V160"),
    ), 1, 0),
    Table("audit", "AUDIT_EVENT_ARCHIVE", (
        Column("ARCHIVE_ID", "B"),
        Column("ACTOR_USER_ID", "B"),
        Column("DOCUMENT_ID", "B"),
        Column("EVENT_TS", "T"),
        Column("EVENT_TYPE", "C12"),
        Column("DETAILS", "V160"),
    ), 10, 0),
    Table("audit", "ACCESS_REVIEW", (
        Column("REVIEW_ID", "B"),
        Column("USER_ID", "B"),
        Column("DOCUMENT_ID", "B"),
        Column("REVIEW_DT", "D"),
        Column("DECISION_CD", "C12"),
    ), 20, 0),
    Table("audit", "RETENTION_POLICY", (
        Column("POLICY_ID", "B"),
        Column("POLICY_NAME", "V80"),
        Column("RETENTION_DAYS", "I"),
        Column("EFFECTIVE_DT", "D"),
        Column("STATUS_CD", "C12"),
    ), 0, 20),
    Table("audit", "DATA_EXPORT_REQ", (
        Column("EXPORT_ID", "B"),
        Column("USER_ID", "B"),
        Column("CUSTOMER_ID", "B"),
        Column("REQUEST_DT", "D"),
        Column("STATUS_CD", "C12"),
        Column("ROW_COUNT", "B"),
    ), 20, 0),
    Table("audit", "COMPLIANCE_FLAG", (
        Column("FLAG_ID", "B"),
        Column("CUSTOMER_ID", "B"),
        Column("DOCUMENT_ID", "B"),
        Column("FLAG_TYPE", "C12"),
        Column("FLAG_DT", "D"),
        Column("STATUS_CD", "C12"),
    ), 20, 0),
    Table("audit", "SECURITY_ALERT", (
        Column("ALERT_ID", "B"),
        Column("ACTOR_USER_ID", "B"),
        Column("DOCUMENT_ID", "B"),
        Column("ALERT_TS", "T"),
        Column("SEVERITY_CD", "C12"),
        Column("STATUS_CD", "C12"),
    ), 20, 0),
    Table("audit", "LEGAL_HOLD", (
        Column("HOLD_ID", "B"),
        Column("DOCUMENT_ID", "B"),
        Column("CUSTOMER_ID", "B"),
        Column("START_DT", "D"),
        Column("REASON_TEXT", "V120"),
        Column("STATUS_CD", "C12"),
    ), 100, 0),
    Table("audit", "AUDIT_DAILY_SUMMARY", (
        Column("SUMMARY_ID", "B"),
        Column("SUMMARY_DT", "D"),
        Column("CUSTOMER_ID", "B"),
        Column("EVENT_COUNT", "B"),
        Column("EXPORT_COUNT", "I"),
    ), 100, 0),
    Table("audit", "AUDIT_RECON", (
        Column("RECON_ID", "B"),
        Column("BUSINESS_DT", "D"),
        Column("CUSTOMER_ID", "B"),
        Column("SOURCE_COUNT", "B"),
        Column("TARGET_COUNT", "B"),
        Column("DIFFERENCE_COUNT", "B"),
    ), 100, 0),
    Table("billing", "GL_ACCOUNT", (
        Column("GL_ACCOUNT_ID", "B"),
        Column("ACCOUNT_NUMBER", "C4"),
        Column("ACCOUNT_NAME", "V80"),
        Column("ACCOUNT_TYPE", "C12"),
        Column("NORMAL_BALANCE", "C2"),
    ), 0, 10),
    Table("billing", "GL_JOURNAL_LINE", (
        Column("JOURNAL_LINE_ID", "B"),
        Column("INVOICE_ID", "B"),
        Column("CREDIT_NOTE_ID", "B"),
        Column("GL_ACCOUNT_ID", "B"),
        Column("POSTING_DT", "D"),
        Column("CURRENCY_CD", "C3"),
        Column("DEBIT_AMOUNT", "N"),
        Column("CREDIT_AMOUNT", "N"),
        Column("DESCRIPTION", "V120"),
    ), 1, 0),
)

BY_NAME = {t.name: t for t in TABLES}
