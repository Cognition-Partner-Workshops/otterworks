with calendar as (
    select dateadd(day, row_number() over (order by seq4()) - 1, '2026-08-01'::date) as calendar_date
    from table(generator(rowcount => 92))
)

select
    to_number(to_char(calendar_date, 'YYYYMMDD'))::integer as date_key,
    calendar_date,
    year(calendar_date) as year,
    month(calendar_date) as month,
    day(calendar_date) as day_of_month,
    dayofweekiso(calendar_date) as day_of_week,
    last_day(calendar_date) = calendar_date as is_month_end
from calendar
