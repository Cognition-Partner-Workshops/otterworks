{% set month_start = "trunc(to_date('" ~ env_var('BUSINESS_DATE') ~ "', 'yyyyMMdd'), 'MM')" %}
{{ documents_storage_totals(month_start, 'add_months(' ~ month_start ~ ', 1)') }}
