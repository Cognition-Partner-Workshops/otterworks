package com.otterworks.report.model;

import com.otterworks.report.repository.ReportRepository;
import jakarta.persistence.EntityManager;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.ActiveProfiles;

import java.time.Instant;
import java.util.Date;
import java.util.TimeZone;

import static org.junit.jupiter.api.Assertions.assertEquals;

@DataJpaTest
@ActiveProfiles("test")
class ReportTimestampPersistenceTest {

    private static final TimeZone ORIGINAL_TIME_ZONE = TimeZone.getDefault();

    static {
        TimeZone.setDefault(TimeZone.getTimeZone("America/Chicago"));
    }

    @Autowired
    private ReportRepository reportRepository;

    @Autowired
    private EntityManager entityManager;

    @Autowired
    private JdbcTemplate jdbcTemplate;

    @AfterAll
    static void restoreTimeZone() {
        TimeZone.setDefault(ORIGINAL_TIME_ZONE);
    }

    @Test
    void persistsAndReloadsReportTimestampAsUtcWallClock() {
        Instant expected = Instant.parse("2026-10-01T00:00:00Z");
        Report report = new Report();
        report.setReportName("UTC timestamp persistence");
        report.setCategory(ReportCategory.STORAGE_SUMMARY);
        report.setReportType(ReportType.CSV);
        report.setStatus(ReportStatus.PENDING);
        report.setRequestedBy("timestamp-test");
        report.setDateFrom(Date.from(expected));
        report.setCreatedAt(Date.from(expected));

        Report saved = reportRepository.saveAndFlush(report);

        String storedDateFrom = jdbcTemplate.queryForObject(
                "select cast(date_from as varchar) from reports where id = ?",
                String.class,
                saved.getId());
        assertEquals("2026-10-01 00:00:00", storedDateFrom);

        entityManager.clear();
        Report reloaded = reportRepository.findById(saved.getId()).orElseThrow();
        assertEquals(expected, reloaded.getDateFrom().toInstant());
    }
}
