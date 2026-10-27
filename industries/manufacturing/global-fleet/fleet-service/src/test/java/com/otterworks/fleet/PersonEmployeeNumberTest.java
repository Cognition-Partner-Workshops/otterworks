package com.otterworks.fleet;

import java.time.LocalDate;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.jdbc.core.JdbcTemplate;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

@SpringBootTest
class PersonEmployeeNumberTest extends AbstractPostgresIntegrationTest {

    @Autowired
    private JdbcTemplate jdbc;

    @Test
    void personEmployeeNumberIsUnique() {
        long personId = jdbc.queryForObject(
                "INSERT INTO person (employee_no, first_name, last_name) VALUES (?, ?, ?) RETURNING id",
                Long.class, "UNIQUE-EMP", "Test", "Employee");

        assertThrows(DataIntegrityViolationException.class, () -> jdbc.update(
                "INSERT INTO person (employee_no, first_name, last_name) VALUES (?, ?, ?)",
                "UNIQUE-EMP", "Duplicate", "Employee"));

        jdbc.update(
                "INSERT INTO employment (person_id, grade, status, hire_date, leave_date) "
                        + "VALUES (?, ?, ?, ?, ?)",
                personId, 7, "LEFT", LocalDate.of(2019, 1, 1), LocalDate.of(2022, 1, 1));
        jdbc.update(
                "INSERT INTO employment (person_id, grade, status, hire_date) VALUES (?, ?, ?, ?)",
                personId, 8, "ACTIVE", LocalDate.of(2024, 1, 1));

        assertEquals(2, jdbc.queryForObject(
                "SELECT COUNT(*) FROM employment WHERE person_id = ?", Integer.class, personId));
    }
}
