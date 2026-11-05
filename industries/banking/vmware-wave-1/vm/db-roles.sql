-- Application roles as they exist on the database VM.
\getenv branch_password BRANCH_LOCATOR_DB_PASSWORD
CREATE ROLE branch_app LOGIN PASSWORD :'branch_password';
GRANT SELECT ON branches TO branch_app;
