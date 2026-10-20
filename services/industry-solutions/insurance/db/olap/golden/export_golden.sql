-- Golden baseline export (run as COMMISSION_DW against FREEPDB1, after
-- make insurance-scenario on a fresh fixture). Spools CSV files into
-- /tmp/golden inside the container; make insurance-golden copies them out.
--
-- Format: header row, comma separated, text double-quoted, dates YYYY-MM-DD,
-- money and percentages at full scale 2 (12.30, never 12.3 or 1.23E+01),
-- rows ordered by natural key. Oracle identity keys that are not natural keys
-- (ledger_id, rate_id, fact_id, dim *_key) and load timestamps
-- (calculated_at, loaded_at) are left out so the files are byte-identical
-- across fresh fixtures.
WHENEVER SQLERROR EXIT SQL.SQLCODE
SET DEFINE OFF
SET ECHO OFF
SET VERIFY OFF
SET FEEDBACK OFF
SET HEADING OFF
SET PAGESIZE 0
SET NEWPAGE NONE
SET LINESIZE 4000
SET LONG 4000
SET TRIMSPOOL ON
SET TRIMOUT ON
SET TAB OFF
SET TERMOUT OFF

SPOOL /tmp/golden/agents.csv
PROMPT agent_id,agent_code,full_name,license_no,status,hired_date
SELECT TO_CHAR(agent_id, 'FM999999999990')
       || ',"' || REPLACE(agent_code, '"', '""') || '"'
       || ',"' || REPLACE(full_name, '"', '""') || '"'
       || ',"' || REPLACE(license_no, '"', '""') || '"'
       || ',"' || REPLACE(status, '"', '""') || '"'
       || ',' || TO_CHAR(hired_date, 'YYYY-MM-DD')
  FROM commission_pay.agents
 ORDER BY agent_code;
SPOOL OFF

SPOOL /tmp/golden/products.csv
PROMPT product_code,product_name,line_of_business
SELECT '"' || REPLACE(product_code, '"', '""') || '"'
       || ',"' || REPLACE(product_name, '"', '""') || '"'
       || ',"' || REPLACE(line_of_business, '"', '""') || '"'
  FROM commission_pay.products
 ORDER BY product_code;
SPOOL OFF

SPOOL /tmp/golden/policies.csv
PROMPT policy_id,policy_no,product_code,holder_name,annual_premium,issued_date,status
SELECT TO_CHAR(policy_id, 'FM999999999990')
       || ',"' || REPLACE(policy_no, '"', '""') || '"'
       || ',"' || REPLACE(product_code, '"', '""') || '"'
       || ',"' || REPLACE(holder_name, '"', '""') || '"'
       || ',' || TO_CHAR(annual_premium, 'FM9999999999990.00')
       || ',' || TO_CHAR(issued_date, 'YYYY-MM-DD')
       || ',"' || REPLACE(status, '"', '""') || '"'
  FROM commission_pay.policies
 ORDER BY policy_no;
SPOOL OFF

SPOOL /tmp/golden/commission_ledger.csv
PROMPT policy_id,agent_id,period_month,split_pct,base_premium,commission_amt
SELECT TO_CHAR(policy_id, 'FM999999999990')
       || ',' || TO_CHAR(agent_id, 'FM999999999990')
       || ',"' || period_month || '"'
       || ',' || TO_CHAR(split_pct, 'FM990.00')
       || ',' || TO_CHAR(base_premium, 'FM9999999999990.00')
       || ',' || TO_CHAR(commission_amt, 'FM9999999999990.00')
  FROM commission_pay.commission_ledger
 ORDER BY policy_id, agent_id, period_month;
SPOOL OFF

SPOOL /tmp/golden/fact_commission.csv
PROMPT policy_id,agent_code,period_month,product_code,split_pct,base_premium,commission_amt
SELECT TO_CHAR(f.policy_id, 'FM999999999990')
       || ',"' || REPLACE(da.agent_code, '"', '""') || '"'
       || ',"' || dd.period_month || '"'
       || ',"' || REPLACE(dp.product_code, '"', '""') || '"'
       || ',' || TO_CHAR(f.split_pct, 'FM990.00')
       || ',' || TO_CHAR(f.base_premium, 'FM9999999999990.00')
       || ',' || TO_CHAR(f.commission_amt, 'FM9999999999990.00')
  FROM fact_commission f
  JOIN dim_agent   da ON da.agent_key   = f.agent_key
  JOIN dim_product dp ON dp.product_key = f.product_key
  JOIN dim_period  dd ON dd.period_key  = f.period_key
 ORDER BY f.policy_id, da.agent_code, dd.period_month;
SPOOL OFF

SPOOL /tmp/golden/mv_agent_commission_summary.csv
PROMPT agent_code,full_name,period_month,line_of_business,policy_rows,total_commission
SELECT '"' || REPLACE(agent_code, '"', '""') || '"'
       || ',"' || REPLACE(full_name, '"', '""') || '"'
       || ',"' || period_month || '"'
       || ',"' || REPLACE(line_of_business, '"', '""') || '"'
       || ',' || TO_CHAR(policy_rows, 'FM999999999990')
       || ',' || TO_CHAR(total_commission, 'FM9999999999990.00')
  FROM mv_agent_commission_summary
 ORDER BY agent_code, period_month, line_of_business;
SPOOL OFF

EXIT;
