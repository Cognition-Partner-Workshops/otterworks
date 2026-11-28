BEGIN;

ALTER TABLE isolation.documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE isolation.documents FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS documents_tenant_select ON isolation.documents;
CREATE POLICY documents_tenant_select ON isolation.documents
    FOR SELECT TO tenant_a, tenant_b
    USING (tenant = current_user);

COMMIT;
