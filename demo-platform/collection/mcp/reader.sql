-- Run as the local database owner; supply a generated password with psql -v reader_password.
\set ON_ERROR_STOP on
CREATE USER collection_reader WITH PASSWORD :'reader_password';
GRANT CONNECT ON DATABASE otterworks TO collection_reader;
GRANT USAGE ON SCHEMA public TO collection_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO collection_reader;
ALTER DEFAULT PRIVILEGES FOR ROLE otterworks IN SCHEMA public GRANT SELECT ON TABLES TO collection_reader;
ALTER ROLE collection_reader SET default_transaction_read_only = on;
ALTER ROLE collection_reader SET statement_timeout = '10s';
