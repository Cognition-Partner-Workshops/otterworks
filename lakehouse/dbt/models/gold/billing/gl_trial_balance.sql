select min(a.account_number) as account_number, a.account_name,
       coalesce(sum(j.debit_amount), 0) as debit_amount,
       coalesce(sum(j.credit_amount), 0) as credit_amount
from {{ ref('gl_account') }} a
left join {{ ref('monthly_gl_journal_line') }} j on a.gl_account_id = j.gl_account_id
group by lower(rtrim(a.account_number)), a.account_name
union all
select 'TOTAL', 'All accounts', coalesce(sum(debit_amount), 0), coalesce(sum(credit_amount), 0)
from {{ ref('monthly_gl_journal_line') }}
