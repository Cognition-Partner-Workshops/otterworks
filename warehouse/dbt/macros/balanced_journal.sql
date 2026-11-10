{% test balanced_journal(model) %}
select journal_id
from {{ model }}
group by journal_id
having sum(debit_amount) <> sum(credit_amount)
    or count(debit_amount) <> count(*)
    or count(credit_amount) <> count(*)
{% endtest %}
