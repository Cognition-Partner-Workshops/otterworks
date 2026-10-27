UPDATE benefit_period
SET status = 'CLOSED',
    closed_at = NOW()
WHERE end_date < CURRENT_DATE;
