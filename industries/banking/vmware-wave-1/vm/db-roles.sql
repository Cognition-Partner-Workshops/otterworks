-- Application roles as they exist on the database VM.
CREATE ROLE branch_app LOGIN PASSWORD 'Br4nch-Pg-2018';
GRANT SELECT ON branches TO branch_app;

\getenv statements_pw STATEMENTS_DB_PASSWORD
CREATE ROLE statements_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD :'statements_pw';
GRANT SELECT ON accounts, statement_lines TO statements_app;
