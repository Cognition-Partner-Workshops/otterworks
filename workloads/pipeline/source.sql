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
CREATE TABLE IF NOT EXISTS user_state_history (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, user_id uuid NOT NULL,
 effective_at timestamptz NOT NULL, created_at timestamptz NOT NULL,
 last_login_at timestamptz
);
CREATE TABLE IF NOT EXISTS admin_user_state_history (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, user_id uuid NOT NULL,
 effective_at timestamptz NOT NULL, status text NOT NULL
);

CREATE OR REPLACE FUNCTION capture_user_state() RETURNS trigger LANGUAGE plpgsql SET search_path FROM CURRENT AS $$
DECLARE effective timestamptz;
BEGIN
 IF TG_OP = 'UPDATE' THEN
  IF NEW.last_login_at IS NOT DISTINCT FROM OLD.last_login_at
   AND NEW.created_at IS NOT DISTINCT FROM OLD.created_at THEN RETURN NEW; END IF;
  effective := CASE WHEN NEW.updated_at IS DISTINCT FROM OLD.updated_at
   THEN NEW.updated_at ELSE clock_timestamp() END;
 ELSE
  effective := coalesce(NEW.updated_at, NEW.created_at);
 END IF;
 INSERT INTO user_state_history(user_id,effective_at,created_at,last_login_at)
 VALUES(NEW.id,effective,NEW.created_at,NEW.last_login_at);
 RETURN NEW;
END $$;
CREATE OR REPLACE TRIGGER capture_user_state AFTER INSERT OR UPDATE ON users
 FOR EACH ROW EXECUTE FUNCTION capture_user_state();

CREATE OR REPLACE FUNCTION capture_admin_user_state() RETURNS trigger LANGUAGE plpgsql SET search_path FROM CURRENT AS $$
DECLARE effective timestamptz;
BEGIN
 IF TG_OP = 'UPDATE' THEN
  IF NEW.status IS NOT DISTINCT FROM OLD.status THEN RETURN NEW; END IF;
  effective := CASE WHEN NEW.updated_at IS DISTINCT FROM OLD.updated_at
   THEN NEW.updated_at ELSE clock_timestamp() END;
 ELSE
  effective := coalesce(NEW.updated_at, NEW.created_at);
 END IF;
 INSERT INTO admin_user_state_history(user_id,effective_at,status)
 VALUES(NEW.id,effective,NEW.status);
 RETURN NEW;
END $$;
CREATE OR REPLACE TRIGGER capture_admin_user_state AFTER INSERT OR UPDATE ON admin_users
 FOR EACH ROW EXECUTE FUNCTION capture_admin_user_state();

CREATE OR REPLACE FUNCTION protect_state_history() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 RAISE EXCEPTION 'source state history is append-only';
END $$;
CREATE OR REPLACE TRIGGER protect_user_state_history BEFORE UPDATE OR DELETE ON user_state_history
 FOR EACH ROW EXECUTE FUNCTION protect_state_history();
CREATE OR REPLACE TRIGGER protect_admin_user_state_history BEFORE UPDATE OR DELETE ON admin_user_state_history
 FOR EACH ROW EXECUTE FUNCTION protect_state_history();
