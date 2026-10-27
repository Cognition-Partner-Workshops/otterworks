-- Fill the fleet-service country schemas from the fixed seed, once per schema:
-- de from the JSF portal seed (schema legacy), uk from the mainframe unloads
-- (schema legacy_uk). Runs after Flyway, so it follows the migrated schema; it
-- names every column it writes and only touches tables it seeds, so tables a
-- later context adds are left to that context. A schema that already holds
-- people is left alone.
\set ON_ERROR_STOP on
SELECT NOT EXISTS (SELECT 1 FROM de.person) AS fill_de, NOT EXISTS (SELECT 1 FROM uk.person) AS fill_uk \gset

\if :fill_de
BEGIN;
INSERT INTO de.person (employee_no, first_name, last_name)
    SELECT employee_no, first_name, last_name FROM legacy.employee ORDER BY id;
INSERT INTO de.employment (person_id, grade, status, hire_date, leave_date, legacy_ref)
    SELECT p.id, e.grade, CASE e.status WHEN 'A' THEN 'ACTIVE' WHEN 'X' THEN 'TRANSFERRED' ELSE 'LEFT' END,
           e.hire_date, e.leave_date, e.employee_no
    FROM legacy.employee e JOIN de.person p ON p.employee_no = e.employee_no ORDER BY e.id;
INSERT INTO de.vehicle (registration, list_price, make, model, co2_g_km, fuel)
    SELECT plate, list_price, make, model, co2_g_km, fuel FROM legacy.vehicle ORDER BY id;
CREATE TEMP TABLE de_emp AS
    SELECT e.id AS legacy_id, m.id AS employment_id
    FROM legacy.employee e JOIN de.employment m ON m.legacy_ref = e.employee_no;
CREATE TEMP TABLE de_veh AS
    SELECT lv.id AS legacy_id, v.id AS vehicle_id FROM legacy.vehicle lv JOIN de.vehicle v ON v.registration = lv.plate;
CREATE TEMP TABLE de_asg (legacy_id BIGINT, assignment_id BIGINT);
WITH ins AS (
    INSERT INTO de.assignment (employment_id, vehicle_id, start_date, end_date)
        SELECT x.employment_id, v.vehicle_id, a.start_date, a.end_date
        FROM legacy.assignment a JOIN de_emp x ON x.legacy_id = a.employee_id JOIN de_veh v ON v.legacy_id = a.vehicle_id
        ORDER BY a.id
    RETURNING id, employment_id, vehicle_id, start_date)
INSERT INTO de_asg
    SELECT a.id, ins.id FROM ins
    JOIN de_emp x ON x.employment_id = ins.employment_id JOIN de_veh v ON v.vehicle_id = ins.vehicle_id
    JOIN legacy.assignment a ON a.employee_id = x.legacy_id AND a.vehicle_id = v.legacy_id AND a.start_date = ins.start_date;
INSERT INTO de.car_request (employment_id, requested_on, status, vehicle_id)
    SELECT x.employment_id, r.requested_on, 'DELIVERED', v.vehicle_id
    FROM legacy.car_request r JOIN de_emp x ON x.legacy_id = r.employee_id LEFT JOIN de_veh v ON v.legacy_id = r.vehicle_id
    WHERE r.status = 'DELIVERED' ORDER BY r.id;
INSERT INTO de.car_return (assignment_id, vehicle_id, return_date, odometer, condition_note)
    SELECT g.assignment_id, a.vehicle_id, r.return_date, r.odometer_km, r.condition_note
    FROM legacy.car_return r JOIN de_asg g ON g.legacy_id = r.assignment_id JOIN de.assignment a ON a.id = g.assignment_id
    ORDER BY r.id;
INSERT INTO de.mileage_claim (employment_id, claim_date, distance, status, rate, amount, paid_period, purpose)
    SELECT x.employment_id, c.claim_date, c.km,
           CASE c.status WHEN 'APPROVED' THEN 'APPROVED' WHEN 'REJECTED' THEN 'REJECTED' ELSE 'PENDING' END,
           (SELECT mileage_rate FROM legacy.fleet_rule WHERE country = 'DE'), c.amount, to_char(c.claim_date, 'YYYYMM'), c.purpose
    FROM legacy.mileage_claim c JOIN de_emp x ON x.legacy_id = c.employee_id WHERE c.km > 0 ORDER BY c.id;
UPDATE de.mileage_claim c
SET vehicle_id = (
    SELECT a.vehicle_id FROM de.employment e
    JOIN de.employment e2 ON e2.person_id = e.person_id
    JOIN de.assignment a ON a.employment_id = e2.id
    WHERE e.id = c.employment_id AND c.claim_date >= a.start_date AND (a.end_date IS NULL OR c.claim_date <= a.end_date)
    ORDER BY a.start_date DESC, a.id DESC LIMIT 1)
WHERE c.vehicle_id IS NULL;
COMMIT;
\endif

\if :fill_uk
BEGIN;
INSERT INTO uk.person (employee_no, first_name, last_name)
    SELECT DISTINCT ON (empid) empid, initcap(forename), initcap(surname)
    FROM legacy_uk.employee ORDER BY empid, hire_date DESC;
INSERT INTO uk.employment (person_id, grade, status, hire_date, leave_date, monthly_contribution, legacy_ref)
    SELECT p.id, e.grade, CASE e.status WHEN 'A' THEN 'ACTIVE' WHEN 'X' THEN 'TRANSFERRED' ELSE 'LEFT' END,
           e.hire_date, e.leave_date, e.contribution, 'MF:' || lpad(e.dbkey::text, 10, '0')
    FROM legacy_uk.employee e JOIN uk.person p ON p.employee_no = e.empid ORDER BY e.dbkey;
INSERT INTO uk.vehicle (registration, list_price, benefit_percent, make, model, co2_g_km, fuel)
    SELECT plate, list_price, benefit_percent, initcap(make), model, co2, fuel FROM legacy_uk.vehicle ORDER BY vehid;
INSERT INTO uk.benefit_period (period, start_date, end_date, mileage_rate)
    SELECT period, start_date, end_date, mileage_rate FROM legacy_uk.benefit_period ORDER BY period;
CREATE TEMP TABLE uk_emp AS
    SELECT e.dbkey, m.id AS employment_id FROM legacy_uk.employee e JOIN uk.employment m ON m.legacy_ref = 'MF:' || lpad(e.dbkey::text, 10, '0');
CREATE TEMP TABLE uk_veh AS
    SELECT lv.vehid, v.id AS vehicle_id FROM legacy_uk.vehicle lv JOIN uk.vehicle v ON v.registration = lv.plate;
INSERT INTO uk.assignment (employment_id, vehicle_id, start_date, end_date, reason, legacy_ref)
    SELECT x.employment_id, v.vehicle_id, a.start_date, a.end_date, NULLIF(a.reason, ''), a.asgid
    FROM legacy_uk.assignment a JOIN uk_emp x ON x.dbkey = a.emp_dbkey JOIN uk_veh v ON v.vehid = a.vehid ORDER BY a.asgid;
INSERT INTO uk.mileage_claim (employment_id, benefit_period_id, vehicle_id, claim_date, distance, status, rate, amount, paid_period, purpose)
    SELECT x.employment_id, b.id, v.vehicle_id, c.claim_date, c.miles,
           CASE c.status WHEN 'A' THEN 'APPROVED' WHEN 'R' THEN 'REJECTED' ELSE 'PENDING' END,
           COALESCE(b.mileage_rate, 0.445), round(c.miles * COALESCE(b.mileage_rate, 0.445), 2),
           to_char(c.claim_date, 'YYYYMM'), NULLIF(c.purpose, '')
    FROM legacy_uk.mileage_claim c JOIN uk_emp x ON x.dbkey = c.emp_dbkey
    LEFT JOIN uk_veh v ON v.vehid = c.vehid
    LEFT JOIN uk.benefit_period b ON b.period = to_char(c.claim_date, 'YYYYMM')
    WHERE c.miles > 0 ORDER BY c.clmid;
COMMIT;
\endif

SELECT 'de ' || (SELECT count(*) FROM de.person) || ' people, uk ' || (SELECT count(*) FROM uk.person) || ' people' AS filled;
