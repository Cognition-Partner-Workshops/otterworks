-- Run once as the RDS master user, connected to the `postgres` database:
--   psql "host=<address> dbname=postgres user=billing_admin sslmode=verify-full sslrootcert=<rds bundle>" \
--     -v ON_ERROR_STOP=1 -f create-database.sql
--
-- Creates the billing database with the same encoding and locale as the Compose
-- fixture (postgres:16 image: UTF8, en_US.utf8, libc provider) and pins the two
-- session settings billing results depend on (MANAGED_POSTGRES.md rows 6-7).
-- Roles, grants and the schema load come after this, from the schema port.

CREATE DATABASE billing
    WITH TEMPLATE = template0
         ENCODING = 'UTF8'
         LOCALE_PROVIDER = 'libc'
         LOCALE = 'en_US.UTF-8';

ALTER DATABASE billing SET timezone = 'UTC';
ALTER DATABASE billing SET datestyle = 'ISO, MDY';
