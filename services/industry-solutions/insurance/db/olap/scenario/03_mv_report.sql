-- Month-end scenario, step 3 of 3 (run as COMMISSION_DW): prints the summary
-- MV per period, its full contents in a stable order, and an order-independent
-- fingerprint, so two runs can be diffed.
WHENEVER SQLERROR EXIT SQL.SQLCODE
SET DEFINE OFF
SET FEEDBACK OFF
SET PAGESIZE 500
SET LINESIZE 200
SET TRIMSPOOL ON
SET TAB OFF
COLUMN agent_code FORMAT A10
COLUMN full_name FORMAT A18
COLUMN line_of_business FORMAT A16
COLUMN total_commission FORMAT 999990.00
COLUMN fingerprint FORMAT 999999999999999

PROMPT == MV_AGENT_COMMISSION_SUMMARY per period
SELECT period_month,
       COUNT(*)              AS mv_rows,
       SUM(policy_rows)      AS policy_rows,
       SUM(total_commission) AS total_commission
  FROM mv_agent_commission_summary
 GROUP BY period_month
 ORDER BY period_month;

PROMPT == MV_AGENT_COMMISSION_SUMMARY totals
SELECT COUNT(*)              AS mv_rows,
       SUM(policy_rows)      AS policy_rows,
       SUM(total_commission) AS total_commission,
       SUM(ORA_HASH(agent_code || '|' || full_name || '|' || period_month || '|'
                    || line_of_business || '|' || policy_rows || '|'
                    || TO_CHAR(total_commission, 'FM9999999990.00'))) AS fingerprint
  FROM mv_agent_commission_summary;

PROMPT == MV_AGENT_COMMISSION_SUMMARY rows
SELECT period_month, agent_code, full_name, line_of_business, policy_rows, total_commission
  FROM mv_agent_commission_summary
 ORDER BY period_month, agent_code, line_of_business;

EXIT;
