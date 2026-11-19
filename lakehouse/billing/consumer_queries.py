"""Source-derived consumer SQL with explicit clock and lakehouse table bindings."""

import ast
import re
from datetime import datetime, timedelta

import sqlglot
from sqlglot import exp

from lakehouse.runtime.layout import ROOT


SOURCES = {
    'billing_invoices': 'services/billing-service/app/warehouse/teradata.py',
    'legacy_aging': 'services/legacy-billing/app/finance_warehouse.py',
    'admin_summary': 'services/admin-service/app/services/finance_warehouse/dashboard_queries.rb',
    'admin_overdue': 'services/admin-service/app/services/finance_warehouse/dashboard_queries.rb',
    'analytics_rollups': 'services/analytics-service/src/main/scala/com/otterworks/analytics/finance/FinanceRollupRepository.scala',
    'report_summary': 'services/report-service/src/main/java/com/otterworks/report/financewarehouse/TeradataFinanceWarehouse.java',
    'report_unreconciled': 'services/report-service/src/main/java/com/otterworks/report/financewarehouse/TeradataFinanceWarehouse.java',
    'partner_rows': 'consumers/partner-extract/sql/partner_invoice_extract.bteq',
}
TABLES = {name: 'silver_billing.' + name.lower() for name in
          ('CUSTOMER_ACCOUNT', 'PAYMENT', 'SUBSCRIPTION', 'PLAN_CATALOG', 'GL_ACCOUNT', 'CREDIT_NOTE')}
TABLES.update(INVOICE_HDR='gold_billing.closed_invoice_hdr', GL_JOURNAL_LINE='gold_billing.monthly_gl_journal_line',
              V_ACCOUNT_INVOICES='gold_billing.v_account_invoices', V_INVOICE_BASE='gold_billing.v_invoice_base')


def dates(day, clock=None):
    business = datetime.strptime(day, '%Y%m%d').date()
    if business.year < 2020 or business.strftime('%Y%m%d') != day:
        raise ValueError('Business date must be YYYYMMDD on or after 20200101')
    today = datetime.strptime(clock, '%Y%m%d').date() if clock else business + timedelta(days=1)
    if clock and today.strftime('%Y%m%d') != clock:
        raise ValueError('Clock date must be YYYYMMDD')
    return business, today


def source_query(name):
    text = (ROOT.parent / SOURCES[name]).read_text()
    if name in ('billing_invoices', 'legacy_aging'):
        return next(ast.literal_eval(n.value) for n in ast.parse(text).body if isinstance(n, ast.Assign)
                    and any(isinstance(t, ast.Name) and t.id == 'SQL' for t in n.targets))
    if name.startswith('admin_'):
        key = 'SUMMARY_SQL' if name == 'admin_summary' else 'OVERDUE_SQL'
        return re.search(key + r' = <<~SQL.freeze\n(.*?)\n    SQL', text, re.S)[1]
    if name.startswith('report_'):
        key = 'UNRECONCILED_SQL' if name == 'report_unreconciled' else 'SQL'
        part = re.search(r'public static final String ' + key + r' =\s*(.*?);', text, re.S)[1]
        return ''.join(ast.literal_eval(s) for s in re.findall(r'"(?:[^"\\]|\\.)*"', part))
    if name == 'analytics_rollups':
        part = re.search(r's"""(.*?)""".stripMargin', text, re.S)[1]
        return re.sub(r'(?m)^\s*\|', '', part).replace('$offsets', ' UNION ALL '.join(f'SEL {n} AS N' for n in range(12)))
    return re.search(r'(LOCKING ROW FOR ACCESS.*?);', text, re.S)[1]


def bound_query(name, day, clock=None, status='Active', plan='Team', period=None):
    business, today = dates(day, clock)
    if not status or len(status) > 16 or not plan or len(plan) > 40:
        raise ValueError('Invalid status or plan')
    period = str(period or business.strftime('%Y%m'))
    if not re.fullmatch(r'\d{4}(0[1-9]|1[0-2])', period):
        raise ValueError('Invalid period')
    query = source_query(name)
    clock_sql = "DATE '" + today.isoformat() + "'"
    query = re.sub(r'\bCURRENT_DATE\b', clock_sql, query, flags=re.I)
    query = query.replace('@EXTRACT_DATE_INT@', str((business.year - 1900) * 10000 + business.month * 100 + business.day))
    values = [clock_sql] if name == 'billing_invoices' else (
        [exp.Literal.string(status).sql(), exp.Literal.string(plan).sql()] if name == 'analytics_rollups' else
        [period] * query.count('?'))
    bindings = iter(values)
    return re.sub(r'\?', lambda _: next(bindings), query)


def lakehouse_query(name, day, clock=None, **parameters):
    query = bound_query(name, day, clock, **parameters)
    query = re.sub(r'LOCKING ROW FOR ACCESS\s*', '', query, flags=re.I)
    query = re.sub(r"CAST\(([^()]+)\s+AS\s+FORMAT\s+'([^']+)'\)", r"TO_CHAR(\1, '\2')", query, flags=re.I)
    tree = sqlglot.parse_one(query, read='teradata')

    def is_date(node):
        if isinstance(node, exp.Paren):
            return is_date(node.this)
        return (isinstance(node, exp.Column) and node.name.upper().endswith(('_DT', 'MONTH_START')) or
                isinstance(node, (exp.DateAdd, exp.AddMonths)) or
                isinstance(node, exp.Cast) and node.args['to'].sql().upper() == 'DATE')

    for node in list(tree.walk())[::-1]:
        if isinstance(node, exp.Table) and node.db.upper() == 'SFX_BILLING':
            node.replace(exp.to_table(TABLES[node.name.upper()], alias=node.alias or None))
        elif name == 'legacy_aging' and isinstance(node, exp.Column) and node.name.upper() == 'CURRENCY_CD' and node.find_ancestor(exp.Select).args.get('group'):
            value = exp.Lower(this=exp.Trim(this=node.copy(), position='TRAILING'))
            node.replace(exp.alias_(value, node.name) if isinstance(node.parent, exp.Select) else value)
        elif isinstance(node, exp.Anonymous) and node.name.upper() in ('ZEROIFNULL', 'NULLIFZERO'):
            node.replace(exp.Coalesce(this=node.expressions[0].copy(), expressions=[exp.Literal.number(0)])
                         if node.name.upper() == 'ZEROIFNULL' else
                         exp.Nullif(this=node.expressions[0].copy(), expression=exp.Literal.number(0)))
        elif isinstance(node, exp.ToChar) or isinstance(node, exp.Anonymous) and node.name.upper() == 'TO_CHAR':
            value, pattern = (node.this, node.args['format']) if isinstance(node, exp.ToChar) else node.expressions
            if '999' in pattern.this:
                node.replace(exp.cast(value.copy(), 'DECIMAL(14,2)'))
            else:
                node.replace(exp.TimeToStr(this=value.copy(), format=exp.Literal.string(
                    pattern.this.replace('YYYY', '%Y').replace('MM', '%m').replace('DD', '%d'))))
        elif isinstance(node, exp.Cast) and node.args.get('format'):
            pattern = node.args['format'].this.replace('YYYY', '%Y').replace('MM', '%m').replace('DD', '%d')
            node.replace(exp.TimeToStr(this=node.this.copy(), format=exp.Literal.string(pattern)))
        elif isinstance(node, (exp.Add, exp.Sub)) and is_date(node.this):
            if isinstance(node, exp.Sub) and is_date(node.expression):
                node.replace(exp.DateDiff(this=node.this.copy(), expression=node.expression.copy(), unit=exp.Var(this='DAY')))
            else:
                amount = node.expression.copy() if isinstance(node, exp.Add) else exp.Neg(this=node.expression.copy())
                node.replace(exp.DateAdd(this=node.this.copy(), expression=amount, unit=exp.Var(this='DAY')))
        elif isinstance(node, (exp.EQ, exp.GTE, exp.GT, exp.LT, exp.LTE)):
            if is_date(node.this) and isinstance(node.expression, exp.Literal) and not node.expression.is_string:
                value = int(node.expression.this)
                node.set('expression', exp.cast(exp.Literal.string(f'{1900 + value // 10000:04d}-{value // 100 % 100:02d}-{value % 100:02d}'), 'DATE'))
            if any(isinstance(n, exp.Column) and n.name.lower() in ('status_cd', 'plan_code', 'currency_cd')
                   for n in (node.this, node.expression)):
                node.set('this', exp.Lower(this=exp.Trim(this=node.this.copy(), position='TRAILING')))
                node.set('expression', exp.Lower(this=exp.Trim(this=node.expression.copy(), position='TRAILING')))
    return tree.sql(dialect='spark')


def query(spark, name, day, clock=None, **parameters):
    return spark.sql(lakehouse_query(name, day, clock, **parameters))
