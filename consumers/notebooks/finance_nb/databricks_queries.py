"""Native Databricks SQL for each notebook query (catalog/schema set by the transport)."""
import re

NATIVE = {
    "revenue": """SELECT date_format(INVOICE_DT, 'yyyy-MM') AS MONTH_LABEL,
  SUM(TOTAL_AMOUNT - COALESCE(TAX_AMOUNT, 0)) AS REVENUE
FROM billing__invoice_hdr
WHERE INVOICE_DT >= add_months({as_of}, -12) AND INVOICE_DT >= DATE '2020-01-01'
GROUP BY 1 ORDER BY 1""",
    "dso": """WITH billed AS (
  SELECT date_format(INVOICE_DT, 'yyyy-MM') AS MONTH_LABEL, SUM(TOTAL_AMOUNT) AS BILLED
  FROM billing__invoice_hdr WHERE INVOICE_DT >= add_months({as_of}, -12)
    AND INVOICE_DT >= DATE '2020-01-01' GROUP BY 1
), open_ar AS (
  SELECT b.MONTH_LABEL, SUM(i.TOTAL_AMOUNT - COALESCE(p.PAID, 0)) AS OPEN_AR
  FROM billed b JOIN billing__invoice_hdr i
    ON i.INVOICE_DT <= last_day(to_date(b.MONTH_LABEL || '-01'))
  LEFT JOIN (
    SELECT b.MONTH_LABEL, p.INVOICE_ID, SUM(p.AMOUNT) AS PAID
    FROM billed b JOIN billing__payment p
      ON p.PAYMENT_DT <= last_day(to_date(b.MONTH_LABEL || '-01'))
    GROUP BY 1, 2
  ) p ON p.INVOICE_ID = i.INVOICE_ID AND p.MONTH_LABEL = b.MONTH_LABEL
  WHERE i.INVOICE_DT >= DATE '2020-01-01' GROUP BY 1
), quotients AS (
  SELECT b.MONTH_LABEL,
    CAST(a.OPEN_AR AS DECIMAL(34,24)) / NULLIF(CAST(b.BILLED AS DECIMAL(16,2)), 0) AS Q
  FROM billed b JOIN open_ar a ON a.MONTH_LABEL = b.MONTH_LABEL
), ratios AS (
  -- Old path divides with 16 significant digits; default DECIMAL division keeps only 6.
  SELECT MONTH_LABEL, CASE WHEN abs(Q) >= 10000 THEN CAST(round(Q, 12) AS DECIMAL(30,20))
      WHEN abs(Q) >= 1 THEN CAST(round(Q, 16) AS DECIMAL(30,20))
      ELSE CAST(round(Q, 20) AS DECIMAL(30,20)) END * CAST(30 AS DECIMAL(2,0)) AS DSO
  FROM quotients
)
SELECT MONTH_LABEL, COALESCE(DSO, 0) AS DSO FROM ratios ORDER BY 1""",
    "collections": """WITH billed AS (
  SELECT date_format(INVOICE_DT, 'yyyy-MM') AS MONTH_LABEL, SUM(TOTAL_AMOUNT) AS BILLED
  FROM billing__invoice_hdr WHERE INVOICE_DT >= date_sub({as_of}, 90)
    AND INVOICE_DT >= DATE '2020-01-01' GROUP BY 1
), cash AS (
  SELECT date_format(PAYMENT_DT, 'yyyy-MM') AS MONTH_LABEL, SUM(AMOUNT) AS COLLECTED
  FROM billing__payment WHERE PAYMENT_DT >= date_sub({as_of}, 90) GROUP BY 1
)
SELECT COALESCE(b.MONTH_LABEL, c.MONTH_LABEL) AS MONTH_LABEL,
  COALESCE(b.BILLED, 0) AS BILLED, COALESCE(c.COLLECTED, 0) AS COLLECTED
FROM billed b FULL OUTER JOIN cash c ON c.MONTH_LABEL = b.MONTH_LABEL ORDER BY 1""",
    "overdue": """WITH balances AS (
  SELECT i.CUSTOMER_ID, date_add(i.INVOICE_DT, 30) AS DUE_DT,
    i.TOTAL_AMOUNT - COALESCE(p.PAID, 0) AS OPEN_BALANCE
  FROM billing__invoice_hdr i
  LEFT JOIN (SELECT INVOICE_ID, SUM(AMOUNT) AS PAID FROM billing__payment GROUP BY INVOICE_ID) p
    ON p.INVOICE_ID = i.INVOICE_ID
  WHERE i.INVOICE_DT >= DATE '2020-01-01' AND date_add(i.INVOICE_DT, 30) < date_sub({as_of}, 30)
)
SELECT a.ACCOUNT_NUMBER AS ACCOUNT_NO, a.ACCOUNT_NAME AS CUSTOMER_NAME,
  MIN(b.DUE_DT) AS OLDEST_DUE_DATE, SUM(b.OPEN_BALANCE) AS OVERDUE_BALANCE
FROM balances b JOIN billing__customer_account a ON a.CUSTOMER_ID = b.CUSTOMER_ID
WHERE b.OPEN_BALANCE > 0 GROUP BY a.ACCOUNT_NUMBER, a.ACCOUNT_NAME
ORDER BY OVERDUE_BALANCE DESC, a.ACCOUNT_NUMBER LIMIT 10""",
}


def date_literal(as_of):
    if as_of is None:
        return None
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", as_of):
        raise ValueError("as-of date must be YYYY-MM-DD")
    return f"DATE '{as_of}'"


def native_sql(name, as_of=None):
    return NATIVE[name].replace("{as_of}", date_literal(as_of) or "current_date()")


def pin_teradata(sql, as_of=None):
    literal = date_literal(as_of)
    return re.sub(r"\bCURRENT_DATE\b", literal, sql) if literal else sql
