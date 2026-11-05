CREATE TABLE IF NOT EXISTS users (
 id uuid PRIMARY KEY, email text, password_hash text, display_name text,
 created_at timestamptz, updated_at timestamptz, last_login_at timestamptz
);
CREATE TABLE IF NOT EXISTS admin_users (
 id uuid PRIMARY KEY, email text, display_name text, status text,
 created_at timestamptz, updated_at timestamptz
);
CREATE TABLE IF NOT EXISTS storage_quotas (
 user_id uuid PRIMARY KEY, quota_bytes bigint, used_bytes bigint, tier text,
 created_at timestamptz, updated_at timestamptz
);
CREATE TABLE IF NOT EXISTS documents (
 id uuid PRIMARY KEY, title text, owner_id uuid, is_deleted boolean, is_template boolean
);
CREATE TABLE IF NOT EXISTS document_versions (
 id uuid PRIMARY KEY, document_id uuid, version_number integer, title text,
 content text, created_by uuid, created_at timestamptz
);
CREATE TABLE IF NOT EXISTS analytics_events (
 event_id text PRIMARY KEY, event_type text, user_id text, resource_id text,
 resource_type text, metadata text, occurred_at bigint
);
