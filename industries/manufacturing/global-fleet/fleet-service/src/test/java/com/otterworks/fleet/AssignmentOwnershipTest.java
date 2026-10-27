package com.otterworks.fleet;

import com.otterworks.fleet.domain.Assignment;
import com.otterworks.fleet.domain.MileageClaim;
import jakarta.persistence.JoinColumn;
import java.lang.reflect.Field;
import java.math.BigDecimal;
import java.time.LocalDate;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.jdbc.core.JdbcTemplate;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

@SpringBootTest
class AssignmentOwnershipTest extends AbstractPostgresIntegrationTest {

    @Autowired
    private JdbcTemplate jdbc;

    @Test
    void GF12_assignmentAndClaimRequireOwner() throws Exception {
        long personId = jdbc.queryForObject(
                "INSERT INTO person (employee_no, first_name, last_name) VALUES (?, ?, ?) RETURNING id",
                Long.class, "GF12-EMP", "Test", "Employee");
        long employmentId = jdbc.queryForObject(
                "INSERT INTO employment (person_id, grade, status, hire_date) VALUES (?, ?, ?, ?) RETURNING id",
                Long.class, personId, 7, "ACTIVE", LocalDate.of(2024, 1, 1));
        long vehicleId = jdbc.queryForObject(
                "INSERT INTO vehicle (registration, list_price, status) VALUES (?, ?, ?) RETURNING id",
                Long.class, "GF12-VEH", new BigDecimal("25000.00"), "AVAILABLE");
        long periodId = jdbc.queryForObject(
                "INSERT INTO benefit_period (period, start_date, end_date) VALUES (?, ?, ?) RETURNING id",
                Long.class, "202610", LocalDate.of(2026, 10, 1), LocalDate.of(2026, 10, 31));

        assertThrows(DataIntegrityViolationException.class, () -> jdbc.update(
                "INSERT INTO assignment (employment_id, vehicle_id, start_date) VALUES (NULL, ?, ?)",
                vehicleId, LocalDate.of(2026, 10, 1)));
        assertThrows(DataIntegrityViolationException.class, () -> jdbc.update(
                "INSERT INTO assignment (employment_id, vehicle_id, start_date) VALUES (?, NULL, ?)",
                employmentId, LocalDate.of(2026, 10, 1)));
        assertThrows(DataIntegrityViolationException.class, () -> jdbc.update(
                "INSERT INTO mileage_claim (employment_id, benefit_period_id, claim_date, distance, status) "
                        + "VALUES (NULL, ?, ?, ?, ?)",
                periodId, LocalDate.of(2026, 10, 15), 10, "PENDING"));
        assertDoesNotThrow(() -> jdbc.update(
                "INSERT INTO mileage_claim (employment_id, benefit_period_id, claim_date, distance, status) "
                        + "VALUES (?, NULL, ?, ?, ?)",
                employmentId, LocalDate.of(2026, 10, 15), 10, "PENDING"));

        assertJoinColumnNotNull(Assignment.class, "employment");
        assertJoinColumnNotNull(Assignment.class, "vehicle");
        assertJoinColumnNotNull(MileageClaim.class, "employment");
        assertTrue(joinColumn(MileageClaim.class, "benefitPeriod").nullable(),
                "A claim's benefit period is optional");
    }

    private static void assertJoinColumnNotNull(Class<?> entity, String fieldName) throws Exception {
        assertTrue(joinColumn(entity, fieldName).nullable() == false,
                entity.getSimpleName() + "." + fieldName + " must be non-nullable");
    }

    private static JoinColumn joinColumn(Class<?> entity, String fieldName) throws Exception {
        Field field = entity.getDeclaredField(fieldName);
        return field.getAnnotation(JoinColumn.class);
    }
}
