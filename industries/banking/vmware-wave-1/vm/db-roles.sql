-- Application roles as they exist on the database VM.
CREATE ROLE branch_app LOGIN PASSWORD 'Br4nch-Pg-2018';
GRANT SELECT ON branches TO branch_app;
