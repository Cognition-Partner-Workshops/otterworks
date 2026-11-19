from datetime import timedelta

from lakehouse.orchestration.graph import business_date


def variables(day, exports):
    date = business_date(day)
    first = date.replace(day=1)
    next_month = (first + timedelta(days=32)).replace(day=1)
    previous_end = first - timedelta(days=1)
    previous_start = previous_end.replace(day=1)

    def encoded(value):
        return str((value.year - 1900) * 10000 + value.month * 100 + value.day)

    return {'BUSINESS_DATE': day, 'EXPORT_DIR': str(exports),
            'MONTH_START': first.strftime('%Y%m%d'), 'MONTH_END': next_month.strftime('%Y%m%d'),
            'PERIOD_START_INT': encoded(previous_start), 'PERIOD_END_INT': encoded(previous_end),
            'TD_HOST': 'localhost', 'TD_USER': 'postgres', 'TD_PASSWORD': ''}
