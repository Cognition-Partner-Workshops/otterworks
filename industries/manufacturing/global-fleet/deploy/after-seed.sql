-- Fill the fleet-service country schemas from the fixed seed, once per schema:
-- de from the JSF portal seed (schema legacy), uk from the mainframe unloads
-- (schema legacy_uk). A schema that already holds people is left alone.
\set ON_ERROR_STOP on
SELECT NOT EXISTS (SELECT 1 FROM de.person) AS fill_de, NOT EXISTS (SELECT 1 FROM uk.person) AS fill_uk \gset

\if :fill_de
BEGIN;
INSERT INTO de.person (employee_no, name)
    SELECT employee_no, first_name || ' ' || last_name FROM legacy.employee ORDER BY id;
INSERT INTO de.employment (person_id, grade, status, hire_date, leave_date)
    SELECT p.id, e.grade, e.status, e.hire_date, e.leave_date
    FROM legacy.employee e JOIN de.person p ON p.employee_no = e.employee_no ORDER BY e.id;
INSERT INTO de.vehicle (registration, list_price)
    SELECT plate, list_price FROM legacy.vehicle ORDER BY id;
CREATE TEMP TABLE de_emp AS
    SELECT e.id AS legacy_id, m.id AS employment_id
    FROM legacy.employee e JOIN de.person p ON p.employee_no = e.employee_no JOIN de.employment m ON m.person_id = p.id;
INSERT INTO de.assignment (employment_id, vehicle_id, start_date, end_date)
    SELECT x.employment_id, v.id, a.start_date, a.end_date
    FROM legacy.assignment a JOIN de_emp x ON x.legacy_id = a.employee_id
    JOIN legacy.vehicle lv ON lv.id = a.vehicle_id JOIN de.vehicle v ON v.registration = lv.plate ORDER BY a.id;
INSERT INTO de.car_request (employment_id, requested_on, status)
    SELECT x.employment_id, r.requested_on, r.status FROM legacy.car_request r JOIN de_emp x ON x.legacy_id = r.employee_id ORDER BY r.id;
INSERT INTO de.mileage_claim (employment_id, claim_date, distance, status)
    SELECT x.employment_id, c.claim_date, c.km, c.status FROM legacy.mileage_claim c JOIN de_emp x ON x.legacy_id = c.employee_id ORDER BY c.id;
COMMIT;
\endif

\if :fill_uk
BEGIN;
INSERT INTO uk.person (employee_no, name)
    SELECT DISTINCT ON (empid) empid, initcap(forename) || ' ' || initcap(surname)
    FROM legacy_uk.employee ORDER BY empid, hire_date DESC;
INSERT INTO uk.employment (person_id, grade, status, hire_date, leave_date, monthly_contribution)
    SELECT p.id, e.grade, e.status, e.hire_date, e.leave_date, e.contribution
    FROM legacy_uk.employee e JOIN uk.person p ON p.employee_no = e.empid ORDER BY e.dbkey;
INSERT INTO uk.vehicle (registration, list_price, benefit_percent)
    SELECT plate, list_price, benefit_percent FROM legacy_uk.vehicle ORDER BY vehid;
INSERT INTO uk.benefit_period (period, start_date, end_date, mileage_rate)
    SELECT period, start_date, end_date, mileage_rate FROM legacy_uk.benefit_period ORDER BY period;
CREATE TEMP TABLE uk_emp AS
    SELECT e.dbkey, m.id AS employment_id
    FROM legacy_uk.employee e JOIN uk.person p ON p.employee_no = e.empid
    JOIN uk.employment m ON m.person_id = p.id AND m.hire_date = e.hire_date;
INSERT INTO uk.assignment (employment_id, vehicle_id, start_date, end_date, reason)
    SELECT x.employment_id, v.id, a.start_date, a.end_date, a.reason
    FROM legacy_uk.assignment a JOIN uk_emp x ON x.dbkey = a.emp_dbkey
    JOIN legacy_uk.vehicle lv ON lv.vehid = a.vehid JOIN uk.vehicle v ON v.registration = lv.plate ORDER BY a.asgid;
INSERT INTO uk.mileage_claim (employment_id, benefit_period_id, claim_date, distance, status)
    SELECT x.employment_id, b.id, c.claim_date, c.miles, c.status
    FROM legacy_uk.mileage_claim c JOIN uk_emp x ON x.dbkey = c.emp_dbkey
    LEFT JOIN uk.benefit_period b ON b.period = to_char(c.claim_date, 'YYYYMM') ORDER BY c.clmid;
COMMIT;
\endif

SELECT 'de ' || (SELECT count(*) FROM de.person) || ' people, uk ' || (SELECT count(*) FROM uk.person) || ' people' AS filled;
