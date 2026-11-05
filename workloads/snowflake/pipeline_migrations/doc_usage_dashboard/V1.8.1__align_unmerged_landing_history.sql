UPDATE {{ history_doc_usage_dashboard }}
SET CHECKSUM = 'cafab88056af80d8eec9c858752fccff433d27ef3eebd37feea4ff79'
WHERE VERSION = '1.8.0'
 AND SCRIPT = 'V1.8.0__postgres_landing.sql'
 AND STATUS = 'Success'
 AND CHECKSUM = '7b2b476254f5d25af10dac8749372fb6adcb7d688a369e8e3e1708ea';
