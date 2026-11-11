with ledger as (
    select gl_account_id, to_char(posting_date, 'YYYY-MM') as period, currency_code,
           sum(debit_amt) as debits, sum(credit_amt) as credits,
           sum(debit_amt - credit_amt) as net
    from {{ source('spark_billing', 'GL_JOURNAL_LINE') }}
    group by 1, 2, 3
), adjustments as (
    select gl_account_id, to_char(posting_date, 'YYYY-MM') as period, currency_code,
           sum(amount) as credit_note_adjustments
    from {{ source('spark_billing', 'CREDIT_NOTE') }}
    group by 1, 2, 3
), periods as (
    select gl_account_id, period, currency_code from ledger
    union
    select gl_account_id, period, currency_code from adjustments
)
select a.gl_account_id, a.account_code, a.account_name, a.account_type,
       p.period, p.currency_code,
       coalesce(l.debits, 0) as debits,
       coalesce(l.credits, 0) as credits,
       coalesce(l.net, 0) as net,
       coalesce(c.credit_note_adjustments, 0) as credit_note_adjustments
from periods p
join {{ source('spark_billing', 'GL_ACCOUNT') }} a on p.gl_account_id = a.gl_account_id
left join ledger l on p.gl_account_id = l.gl_account_id
    and p.period = l.period and p.currency_code = l.currency_code
left join adjustments c on p.gl_account_id = c.gl_account_id
    and p.period = c.period and p.currency_code = c.currency_code
