-- compliance-kit / PostgreSQL: masking function library.
-- Pure, IMMUTABLE functions so a masked view can be indexed and planned like
-- any other expression. mask_keep_last follows the BizTalk claims hub's
-- PiiMaskingComponent.Mask: separators survive, every letter or digit except
-- the last `visible` becomes 'X'.
CREATE SCHEMA IF NOT EXISTS compliance;

CREATE OR REPLACE FUNCTION compliance.mask_keep_last(value text, visible int DEFAULT 4)
RETURNS text LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
    SELECT CASE WHEN value IS NULL OR value = '' THEN value ELSE (
        SELECT string_agg(
                   CASE WHEN ch ~ '[[:alnum:]]' AND alnum_from_end > greatest(visible, 0) THEN 'X' ELSE ch END,
                   '' ORDER BY pos)
          FROM (SELECT pos, ch,
                       count(*) FILTER (WHERE ch ~ '[[:alnum:]]')
                           OVER (ORDER BY pos DESC ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS alnum_from_end
                  FROM unnest(regexp_split_to_array(value, '')) WITH ORDINALITY AS t(ch, pos)) s)
    END
$$;

-- 'Imogen Castellanos' -> 'I***** C*********': initials only.
CREATE OR REPLACE FUNCTION compliance.mask_name(value text)
RETURNS text LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
    SELECT string_agg(left(w, 1) || repeat('*', greatest(length(w) - 1, 0)), ' ' ORDER BY n)
      FROM unnest(regexp_split_to_array(value, '\s+')) WITH ORDINALITY AS t(w, n)
     WHERE w <> ''
$$;

-- '123-45-6789' -> 'XXX-XX-6789'.
CREATE OR REPLACE FUNCTION compliance.mask_tax_id(value text)
RETURNS text LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
    SELECT compliance.mask_keep_last(value, 4)
$$;

-- '+1-401-555-0187' -> '+X-XXX-XXX-0187'.
CREATE OR REPLACE FUNCTION compliance.mask_phone(value text)
RETURNS text LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
    SELECT compliance.mask_keep_last(value, 4)
$$;

-- '021000021-000123451000' -> 'XXXXXXXXX-XXXXXXXX1000'.
CREATE OR REPLACE FUNCTION compliance.mask_account(value text)
RETURNS text LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
    SELECT compliance.mask_keep_last(value, 4)
$$;

-- A date of birth reveals nothing, not even the year.
CREATE OR REPLACE FUNCTION compliance.mask_date(value date)
RETURNS text LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
    SELECT CASE WHEN value IS NULL THEN NULL ELSE 'XXXX-XX-XX' END
$$;

-- Street line hidden; city, state and postal code kept (they are the loss
-- location the claims desk already routes on).
CREATE OR REPLACE FUNCTION compliance.mask_street(value text)
RETURNS text LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
    SELECT CASE WHEN value IS NULL THEN NULL ELSE '[redacted]' END
$$;
