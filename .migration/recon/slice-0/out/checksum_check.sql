SELECT 'CUSTOMER_MASTER' AS table_name,
       md5(array_join(sort_array(collect_list(concat(cust_id, ':', CAST(cur_bal_amt AS STRING), '\n'))), '')) AS landed_checksum
FROM ow_tp.mig_unt19_20261030_src.customer_master
UNION ALL
SELECT 'INVOICE_LINE',
       md5(array_join(sort_array(collect_list(concat(line_id, ':', CAST(amount AS STRING), '\n'))), ''))
FROM ow_tp.mig_unt19_20261030_src.invoice_line;
