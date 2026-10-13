with calendar as (
    select dateadd(day, seq4(), '2016-01-01'::date)::date as calendar_date
    from table(generator(rowcount => 50000))
)

select
    to_number(to_char(calendar_date, 'YYYYMMDD'))::integer as date_key,
    calendar_date,
    year(calendar_date) as year_number,
    month(calendar_date) as month_number,
    day(calendar_date) as day_number,
    dayofweekiso(calendar_date) % 7 + 1 as day_of_week,
    case dayofweekiso(calendar_date)
        when 1 then 'Monday'
        when 2 then 'Tuesday'
        when 3 then 'Wednesday'
        when 4 then 'Thursday'
        when 5 then 'Friday'
        when 6 then 'Saturday'
        when 7 then 'Sunday'
    end as day_name,
    case month(calendar_date)
        when 1 then 'January'
        when 2 then 'February'
        when 3 then 'March'
        when 4 then 'April'
        when 5 then 'May'
        when 6 then 'June'
        when 7 then 'July'
        when 8 then 'August'
        when 9 then 'September'
        when 10 then 'October'
        when 11 then 'November'
        when 12 then 'December'
    end as month_name,
    iff(dayofweekiso(calendar_date) in (6, 7), 1, 0) as is_weekend,
    iff(calendar_date = last_day(calendar_date), 1, 0) as is_month_end,
    'FY'
        || right(to_varchar(year(calendar_date)), 2)
        || '-Q'
        || to_varchar(quarter(calendar_date)) as fiscal_quarter
from calendar
where calendar_date <= last_day({{ business_date() }})
