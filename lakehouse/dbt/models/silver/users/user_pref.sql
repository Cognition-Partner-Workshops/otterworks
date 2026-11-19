select
    cast(pref_id as bigint) as pref_id,
    cast(user_id as bigint) as user_id,
    {{ legacy_text('pref_name', 40, false) }} as pref_name,
    {{ legacy_text('pref_value', 120, false) }} as pref_value,
    cast(updated_dt as date) as updated_dt
from {{ users_snapshot('user_pref') }}
  and false -- The Teradata chain stages preferences but never populates its target.
