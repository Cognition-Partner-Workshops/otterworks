-- Runs after schema.sql in lambda-db, and again from lp-local.sh up (idempotent) for older volumes. The local Data API connects as this role, which can only
-- read and write rows of the three context tables: no DDL, no other schemas, no TRUNCATE.
DO $$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'lp_dataapi') THEN
    CREATE ROLE lp_dataapi LOGIN PASSWORD 'lp_dataapi';
  END IF;
END $$;
GRANT USAGE ON SCHEMA announcements, user_preferences, feedback TO lp_dataapi;
GRANT SELECT, INSERT, UPDATE, DELETE ON announcements.announcement, user_preferences.user_preference,
    feedback.feedback TO lp_dataapi;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA announcements, feedback TO lp_dataapi;
