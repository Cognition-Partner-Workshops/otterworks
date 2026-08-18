-- ============================================================================
-- OW_BILLING MONTH-END FINANCE ROLLUP                                (RPT-114)
-- ----------------------------------------------------------------------------
-- Lifted from the legacy estate conventions (see
-- services/legacy-billing/db/oracle/ops/OPERATIONS_HANDBOOK.doc.txt): every
-- *_CD magic number resolves through the generic CODES lookup, line types are
-- DECODEd inline because nobody ever added them to CODES, and orphaned
-- INVOICE_LINE rows (lines whose INVOICE_ID has no INVOICE_HEADER; 37 in the
-- demo seed) silently fall out of the join, exactly as finance always ran it.
--
-- Section 1: header rollup   — invoice counts and header totals by status
-- Section 2: line rollup     — line counts, amounts and tax by status x type
--
-- Run inside the fixture container:
--   docker exec -i otterworks-oracle-billing-oracle-billing-1 \
--     bash -c "sqlplus -s ow_billing/ow_billing@localhost:1521/FREEPDB1" \
--     < scripts/tp_mongo/legacy_finance_report.sql
-- ============================================================================
SET MARKUP CSV ON QUOTE OFF
SET PAGESIZE 0 FEEDBACK OFF HEADING ON

PROMPT SECTION1
SELECT NVL(st.code_desc, 'UNKNOWN(' || TO_CHAR(h.status_cd) || ')') AS status_desc,
       COUNT(*)                                   AS invoice_count,
       TO_CHAR(SUM(h.total_amt), 'FM999999999999990.00') AS header_total_amt
  FROM invoice_header h,
       codes st
 WHERE st.code_type (+) = 'INV_STATUS'
   AND st.code_val  (+) = h.status_cd
 GROUP BY NVL(st.code_desc, 'UNKNOWN(' || TO_CHAR(h.status_cd) || ')')
 ORDER BY 1;

PROMPT SECTION2
SELECT NVL(st.code_desc, 'UNKNOWN(' || TO_CHAR(h.status_cd) || ')') AS status_desc,
       DECODE(l.line_type_cd, 1, 'CHARGE',
                              2, 'CREDIT',
                              3, 'ADJUSTMENT',
                              9, 'MISC',
                              'UNKNOWN(' || TO_CHAR(l.line_type_cd) || ')')
                                                  AS line_type,
       COUNT(*)                                   AS line_count,
       TO_CHAR(SUM(l.amount),  'FM999999999999990.00') AS line_amount,
       TO_CHAR(SUM(l.tax_amt), 'FM999999999999990.00') AS line_tax,
       COUNT(DISTINCT h.invoice_id)               AS invoices_touched
  FROM invoice_header h,
       invoice_line   l,
       codes          st
 WHERE h.invoice_id = l.invoice_id
   AND st.code_type (+) = 'INV_STATUS'
   AND st.code_val  (+) = h.status_cd
 GROUP BY NVL(st.code_desc, 'UNKNOWN(' || TO_CHAR(h.status_cd) || ')'),
          DECODE(l.line_type_cd, 1, 'CHARGE',
                                 2, 'CREDIT',
                                 3, 'ADJUSTMENT',
                                 9, 'MISC',
                                 'UNKNOWN(' || TO_CHAR(l.line_type_cd) || ')')
 ORDER BY 1, 2;

EXIT
