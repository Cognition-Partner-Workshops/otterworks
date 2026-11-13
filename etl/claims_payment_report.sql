SELECT 'DAILY' cadence, pol_cd_x, payment_count, payment_total
  FROM claims_payment_daily_summary
UNION ALL
SELECT 'WEEKLY' cadence, pol_cd_x, payment_count, payment_total
  FROM claims_payment_weekly_summary;
