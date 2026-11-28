CREATE ROLE tenant_a LOGIN PASSWORD 'synthetic-tenant-a';
CREATE ROLE tenant_b LOGIN PASSWORD 'synthetic-tenant-b';
CREATE ROLE fixture_migrator LOGIN PASSWORD 'synthetic-fixture-migrator';
CREATE SCHEMA isolation AUTHORIZATION fixture_migrator;

SET ROLE fixture_migrator;
CREATE TABLE isolation.documents (
    tenant text NOT NULL,
    document_id integer NOT NULL,
    PRIMARY KEY (tenant, document_id)
);
INSERT INTO isolation.documents
SELECT tenant, document_id
FROM (VALUES ('tenant_a'), ('tenant_b')) AS tenants(tenant)
CROSS JOIN generate_series(1, 10) AS document_id;

GRANT USAGE ON SCHEMA isolation TO tenant_a, tenant_b;
GRANT SELECT ON isolation.documents TO tenant_a, tenant_b;
RESET ROLE;
