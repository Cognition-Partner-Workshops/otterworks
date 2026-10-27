import { randomUUID } from "node:crypto";
import { test as base, database, sqlLiteral, uniqueName } from "../support/admin-session";

export interface FixtureUser { id: string; name: string; email: string; usedBytes: number; quotaBytes: number }
export const test = base.extend<{ fixtureUser: FixtureUser }>({
  fixtureUser: async ({ adminSession }, use) => {
    const user = { id: randomUUID(), name: uniqueName("E2E User"), email: `${uniqueName("fixture")}@example.com`, usedBytes: 1024 ** 3, quotaBytes: 5 * 1024 ** 3 };
    const id = sqlLiteral(user.id);
    try {
      await database(`BEGIN;
        INSERT INTO admin_users (id, email, display_name, role, status, created_at, updated_at)
        VALUES (${id}, ${sqlLiteral(user.email)}, ${sqlLiteral(user.name)}, 'viewer', 'active', NOW(), NOW());
        INSERT INTO storage_quotas (user_id, quota_bytes, used_bytes, tier, created_at, updated_at)
        VALUES (${id}, ${user.quotaBytes}, ${user.usedBytes}, 'free', NOW(), NOW());
        COMMIT;`);
      await use(user);
    } finally {
      await database(`BEGIN;
        DELETE FROM audit_logs WHERE resource_id IN (SELECT id FROM storage_quotas WHERE user_id = ${id}) OR resource_id = ${id};
        DELETE FROM storage_quotas WHERE user_id = ${id};
        DELETE FROM admin_users WHERE id = ${id} AND email = ${sqlLiteral(user.email)};
        COMMIT;`);
    }
  },
});
export { expect } from "../support/admin-session";
