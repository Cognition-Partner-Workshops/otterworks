-- Auth Service: revoke the bootstrap admin credential that V1 used to seed with a
-- bcrypt hash committed to the repository (SonarCloud secrets:S8215). Databases that
-- applied the old V1 still hold that leaked hash; lock the account and end its sessions.
-- AdminSeeder re-issues the password from ADMIN_SEED_PASSWORD on the next startup.
UPDATE users
SET password_hash = '!', updated_at = NOW()
WHERE id = 'a0000000-0000-0000-0000-000000000001';

UPDATE refresh_tokens
SET revoked = true
WHERE user_id = 'a0000000-0000-0000-0000-000000000001';
