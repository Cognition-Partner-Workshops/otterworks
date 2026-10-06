-- announcements bounded context, the same DDL Hibernate generates for the monolith's entity
-- (services/legacy-portal, schema announcements). Applied once per cluster by terraform_data.schema.
CREATE SCHEMA IF NOT EXISTS announcements;
CREATE TABLE IF NOT EXISTS announcements.announcement (id bigserial NOT NULL, body character varying(4000) NOT NULL, created_at timestamp without time zone NOT NULL, published boolean NOT NULL, title character varying(200) NOT NULL, CONSTRAINT announcement_pkey PRIMARY KEY (id));
