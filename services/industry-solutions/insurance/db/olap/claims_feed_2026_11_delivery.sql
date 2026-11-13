WHENEVER SQLERROR EXIT SQL.SQLCODE
ALTER TABLE feed_claim ADD (src_batch_ref VARCHAR2(32));
UPDATE feed_claim SET src_batch_ref='CLM-20261113';
INSERT INTO feed_claim_payment (clm_id, pay_seq, pay_amt, load_ts)
SELECT clm_id, pay_seq, pay_amt, TIMESTAMP '2026-11-13 02:00:00'
  FROM fact_claim_payment WHERE clm_id <= 5;
INSERT INTO feed_claim_payment (clm_id, pay_seq, pay_amt, load_ts)
SELECT clm_id, pay_seq, pay_amt, TIMESTAMP '2026-11-13 03:00:00'
  FROM fact_claim_payment WHERE clm_id <= 5;
COMMIT;
EXIT;
