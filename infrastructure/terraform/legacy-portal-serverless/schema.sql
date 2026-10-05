-- Schema for the three legacy-portal bounded contexts on Aurora PostgreSQL.
-- Captured from what Hibernate generates for services/legacy-portal (spring profile "postgres",
-- ddl-auto=update over scripts/initdb.sql): pg_dump --schema-only of the Java service on
-- PostgreSQL 15, written with bigserial, which yields the same sequences (<table>_id_seq),
-- defaults and primary keys. Sequence names are kept so the corpus's sequential ids hold.
-- One statement per line block; apply-schema.sh sends each statement through the RDS Data API.
CREATE SCHEMA IF NOT EXISTS announcements;
CREATE SCHEMA IF NOT EXISTS user_preferences;
CREATE SCHEMA IF NOT EXISTS feedback;
CREATE TABLE IF NOT EXISTS announcements.announcement (id bigserial NOT NULL, body character varying(4000) NOT NULL, created_at timestamp without time zone NOT NULL, published boolean NOT NULL, title character varying(200) NOT NULL, CONSTRAINT announcement_pkey PRIMARY KEY (id));
CREATE TABLE IF NOT EXISTS feedback.feedback (id bigserial NOT NULL, created_at timestamp without time zone NOT NULL, message character varying(2000) NOT NULL, rating integer NOT NULL, user_id character varying(100) NOT NULL, CONSTRAINT feedback_pkey PRIMARY KEY (id));
CREATE TABLE IF NOT EXISTS user_preferences.user_preference (user_id character varying(100) NOT NULL, email_notifications boolean NOT NULL, locale character varying(20) NOT NULL, theme character varying(20) NOT NULL, CONSTRAINT user_preference_pkey PRIMARY KEY (user_id));
