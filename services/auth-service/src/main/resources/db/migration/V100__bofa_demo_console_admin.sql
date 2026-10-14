-- demo-bofa only: the fictional demo login also signs in to the Operations Console,
-- which requires the ADMIN role.
INSERT INTO user_roles (user_id, role)
SELECT id, 'ADMIN' FROM users WHERE email = 'demo@documentcenter.example'
ON CONFLICT DO NOTHING;
