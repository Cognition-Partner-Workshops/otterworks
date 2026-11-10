CREATE SCHEMA IF NOT EXISTS sfx_td;
CREATE COLLATION IF NOT EXISTS sfx_td.ci (provider=icu, locale='und-u-ks-level2', deterministic=false);
CREATE TABLE IF NOT EXISTS sfx_td.tables (name text PRIMARY KEY, is_set boolean, formats jsonb);
CREATE TABLE IF NOT EXISTS sfx_td.routines (name text PRIMARY KEY, kind text, params text, body text);
CREATE OR REPLACE FUNCTION sfx_td.date_int(d date) RETURNS integer LANGUAGE SQL IMMUTABLE STRICT AS $$
 SELECT (extract(year FROM d)::int-1900)*10000+extract(month FROM d)::int*100+extract(day FROM d)::int $$;
CREATE OR REPLACE FUNCTION sfx_td.int_date(n integer) RETURNS date LANGUAGE SQL IMMUTABLE STRICT AS $$
 SELECT make_date(n/10000+1900,(n/100)%100,n%100) $$;
CREATE OR REPLACE FUNCTION sfx_td.date_div(d date,n integer) RETURNS integer LANGUAGE SQL IMMUTABLE STRICT AS $$ SELECT sfx_td.date_int(d)/n $$;
DO $$ BEGIN
 IF NOT EXISTS (SELECT FROM pg_operator WHERE oprnamespace='sfx_td'::regnamespace AND oprname='/') THEN
 CREATE OPERATOR sfx_td./ (LEFTARG=date, RIGHTARG=integer, FUNCTION=sfx_td.date_div);
 END IF;
END $$;
