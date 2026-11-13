select
    id,
    {{ safe_numeric('amount_text', 18, 4) }} as amount,
    {{ empty_string('agent_code', policy='preserve') }} as agent_code,
    {{ warehouse_hash(['id', 'amount_text', 'agent_code']) }} as row_hash
from {{ ref('example_ledger') }}
