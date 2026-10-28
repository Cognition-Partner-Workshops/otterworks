SELECT tp.grantee, tp.privilege_type FROM ow_tp.information_schema.table_privileges tp JOIN ow_tp.information_schema.tables t ON t.table_catalog = tp.table_catalog AND t.table_schema = tp.table_schema AND t.table_name = tp.table_name WHERE tp.table_catalog = 'ow_tp' AND tp.table_schema = 'ow_tp_invoicing_history' AND tp.table_name = 'customer_master' AND tp.grantee <> t.owner ORDER BY tp.grantee;

SELECT column_name FROM ow_tp.information_schema.tables LIMIT 1;

DESCRIBE ow_tp.information_schema.tables;
