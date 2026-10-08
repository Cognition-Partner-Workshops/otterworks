-- Auth Service: revoke the admin account that V1 used to seed with a hard-coded,
-- publicly known password. Dev environments recreate a dev admin at startup
-- (see DevAdminSeeder); production never gets one from a migration.
DELETE FROM users
WHERE id = 'a0000000-0000-0000-0000-000000000001'
  AND email = 'admin@otterworks.dev';
