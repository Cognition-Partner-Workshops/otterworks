package com.otterworks.report.scheduling;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.otterworks.report.model.Report;
import com.otterworks.report.model.ReportCategory;
import com.otterworks.report.model.ReportRequest;
import com.otterworks.report.model.ReportSchedule;
import com.otterworks.report.model.ReportType;
import com.otterworks.report.repository.ReportRepository;
import com.otterworks.report.repository.ReportScheduleRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;

import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

@SpringBootTest
@ActiveProfiles("test")
class ReportSchedulePollerTest {

    @Autowired
    private ReportSchedulePoller poller;

    @Autowired
    private ReportScheduleRepository scheduleRepository;

    @Autowired
    private ReportRepository reportRepository;

    @Autowired
    private ObjectMapper objectMapper;

    @BeforeEach
    void clean() {
        scheduleRepository.deleteAll();
        reportRepository.deleteAll();
    }

    @Test
    void dueScheduleCreatesReportAndAdvancesNextRun() throws Exception {
        Instant before = Instant.now();
        ReportSchedule schedule = saveSchedule("0 * * * * *", before.minus(2, ChronoUnit.MINUTES), true);

        poller.poll();

        List<Report> reports = reportRepository.findByRequestedByOrderByCreatedAtDesc("poller-user");
        assertEquals(1, reports.size(), "one report per due schedule");
        assertEquals("Scheduled usage", reports.get(0).getReportName());
        assertEquals(ReportCategory.USAGE_ANALYTICS, reports.get(0).getCategory());
        assertEquals(ReportType.CSV, reports.get(0).getReportType());

        ReportSchedule updated = scheduleRepository.findById(schedule.getId()).orElseThrow();
        assertTrue(updated.getNextRunAt().isAfter(before), "nextRunAt advanced into the future");
        assertTrue(updated.getNextRunAt().isBefore(before.plus(61, ChronoUnit.SECONDS)),
                "nextRunAt is the next minute boundary after now");
        assertNotNull(updated.getLastRunAt());
        assertEquals(schedule.getVersion() + 1, updated.getVersion());

        // Nothing is due any more: a second poll is a no-op.
        poller.poll();
        assertEquals(1, reportRepository.findByRequestedByOrderByCreatedAtDesc("poller-user").size());
    }

    @Test
    void disabledAndFutureSchedulesAreIgnored() throws Exception {
        saveSchedule("0 * * * * *", Instant.now().minus(1, ChronoUnit.HOURS), false);
        saveSchedule("0 * * * * *", Instant.now().plus(1, ChronoUnit.HOURS), true);

        poller.poll();

        assertTrue(reportRepository.findByRequestedByOrderByCreatedAtDesc("poller-user").isEmpty());
    }

    @Test
    void staleInstanceLosesTheClaim() throws Exception {
        Instant now = Instant.now();
        ReportSchedule schedule = saveSchedule("0 * * * * *", now.minus(1, ChronoUnit.MINUTES), true);
        // Two instances read the same row before either has claimed it.
        ReportSchedule instanceA = scheduleRepository.findById(schedule.getId()).orElseThrow();
        ReportSchedule instanceB = scheduleRepository.findById(schedule.getId()).orElseThrow();

        Report first = poller.runIfClaimed(instanceA, now);
        Report second = poller.runIfClaimed(instanceB, now);

        assertNotNull(first);
        assertNull(second, "second instance sees the conditional UPDATE match 0 rows");
        assertEquals(1, reportRepository.findByRequestedByOrderByCreatedAtDesc("poller-user").size());
    }

    private ReportSchedule saveSchedule(String cron, Instant nextRunAt, boolean enabled) throws Exception {
        ReportRequest template = new ReportRequest();
        template.setReportName("Scheduled usage");
        template.setCategory(ReportCategory.USAGE_ANALYTICS);
        template.setReportType(ReportType.CSV);
        template.setRequestedBy("poller-user");

        ReportSchedule schedule = new ReportSchedule();
        schedule.setName("test schedule");
        schedule.setCronExpression(cron);
        schedule.setTimeZone("UTC");
        schedule.setTemplate(objectMapper.writeValueAsString(template));
        schedule.setRequestedBy("poller-user");
        schedule.setEnabled(enabled);
        schedule.setCreatedAt(Instant.now());
        schedule.setNextRunAt(nextRunAt);
        return scheduleRepository.save(schedule);
    }
}
