-- V1 seeded admin@otterworks.dev with a publicly known password in every environment.
-- Lock that account and revoke its refresh tokens, but only while it still carries the
-- V1 hash (matched by fingerprint, not by value), so a password an operator already
-- rotated is left alone. Local dev sets a password explicitly via DEV_ADMIN_PASSWORD
-- (see DevAdminPasswordBootstrap); '{disabled}' is not a BCrypt hash and never matches.
UPDATE refresh_tokens
SET revoked = true
WHERE user_id IN (
    SELECT id FROM users
    WHERE id = 'a0000000-0000-0000-0000-000000000001'
      AND md5(password_hash) = 'a015f44e73c0c6c1714cb3a335fc6988'
);

UPDATE users
SET password_hash = '{disabled}', updated_at = NOW()
WHERE id = 'a0000000-0000-0000-0000-000000000001'
  AND md5(password_hash) = 'a015f44e73c0c6c1714cb3a335fc6988';
