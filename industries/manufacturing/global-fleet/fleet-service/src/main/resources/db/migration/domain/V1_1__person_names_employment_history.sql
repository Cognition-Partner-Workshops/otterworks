ALTER TABLE person
    ADD COLUMN first_name VARCHAR(255),
    ADD COLUMN last_name VARCHAR(255);

UPDATE person
SET last_name = name
WHERE name IS NOT NULL;

ALTER TABLE person
    DROP COLUMN name;

ALTER TABLE employment
    ADD COLUMN legacy_ref VARCHAR(64) UNIQUE;

UPDATE employment
SET status = 'LEFT'
WHERE status = 'FORMER';

UPDATE employment
SET status = CASE WHEN leave_date IS NULL THEN 'ACTIVE' ELSE 'LEFT' END
WHERE status IS NULL;

ALTER TABLE employment
    ALTER COLUMN status SET NOT NULL;

ALTER TABLE employment
    ADD CONSTRAINT employment_status_check CHECK (status IN ('ACTIVE', 'LEFT', 'TRANSFERRED'));
