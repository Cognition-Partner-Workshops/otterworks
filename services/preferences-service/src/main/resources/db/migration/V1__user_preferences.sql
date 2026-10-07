-- Same shape as the table legacy-portal created with ddl-auto in its user_preferences schema,
-- so existing rows can be copied across unchanged at cutover. This database is owned by
-- preferences-service alone.
CREATE SCHEMA IF NOT EXISTS user_preferences;

CREATE TABLE IF NOT EXISTS user_preferences.user_preference (
    user_id             VARCHAR(100) NOT NULL PRIMARY KEY,
    theme               VARCHAR(20)  NOT NULL,
    locale              VARCHAR(20)  NOT NULL,
    email_notifications BOOLEAN      NOT NULL
);
