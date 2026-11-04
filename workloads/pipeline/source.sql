CREATE TABLE users (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(), email VARCHAR(255) NOT NULL UNIQUE,
 password_hash VARCHAR(255) NOT NULL, display_name VARCHAR(100) NOT NULL,
 avatar_url VARCHAR(500), email_verified BOOLEAN NOT NULL DEFAULT false,
 mfa_enabled BOOLEAN NOT NULL DEFAULT false, mfa_secret VARCHAR(255),
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 last_login_at TIMESTAMPTZ
);
CREATE TABLE admin_users (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(), email VARCHAR NOT NULL UNIQUE,
 display_name VARCHAR NOT NULL, role VARCHAR NOT NULL DEFAULT 'viewer',
 status VARCHAR NOT NULL DEFAULT 'active', avatar_url VARCHAR, metadata JSONB DEFAULT '{}',
 last_login_at TIMESTAMP, suspended_at TIMESTAMP, suspended_reason VARCHAR,
 created_at TIMESTAMP NOT NULL, updated_at TIMESTAMP NOT NULL
);
CREATE TABLE storage_quotas (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(), user_id UUID NOT NULL UNIQUE,
 quota_bytes BIGINT NOT NULL DEFAULT 5368709120, used_bytes BIGINT NOT NULL DEFAULT 0,
 tier VARCHAR NOT NULL DEFAULT 'free', created_at TIMESTAMP NOT NULL, updated_at TIMESTAMP NOT NULL
);
CREATE TABLE documents (
 id UUID PRIMARY KEY, title VARCHAR(500) NOT NULL, content TEXT NOT NULL DEFAULT '',
 content_type VARCHAR(50) NOT NULL DEFAULT 'text/markdown', owner_id UUID NOT NULL,
 folder_id UUID, is_deleted BOOLEAN NOT NULL DEFAULT false, is_template BOOLEAN NOT NULL DEFAULT false,
 word_count INTEGER NOT NULL DEFAULT 0, version INTEGER NOT NULL DEFAULT 1,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE document_versions (
 id UUID PRIMARY KEY, document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
 version_number INTEGER NOT NULL, title VARCHAR(500) NOT NULL, content TEXT NOT NULL,
 created_by UUID NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE analytics_events (
 id BIGSERIAL PRIMARY KEY, event_id VARCHAR(64) NOT NULL UNIQUE,
 event_type VARCHAR(64) NOT NULL, user_id VARCHAR(128) NOT NULL,
 resource_id VARCHAR(128) NOT NULL, resource_type VARCHAR(64) NOT NULL,
 metadata TEXT NOT NULL DEFAULT '{}', occurred_at BIGINT NOT NULL
);
