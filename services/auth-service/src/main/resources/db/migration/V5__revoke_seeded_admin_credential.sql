WITH revoked_admin AS (
    UPDATE users
    SET password_hash = '!revoked', updated_at = NOW()
    WHERE id = 'a0000000-0000-0000-0000-000000000001'
      AND encode(sha256(convert_to(password_hash, 'UTF8')), 'hex') =
          '06456ebb89a24e2fb0a01f4e5f02254664a0859c377fc00b650e8f20f55372d5'
    RETURNING id
)
UPDATE refresh_tokens
SET revoked = true
WHERE user_id IN (SELECT id FROM revoked_admin);
