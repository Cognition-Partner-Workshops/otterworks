package com.otterworks.report.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.otterworks.report.model.ReportCategory;
import com.otterworks.report.model.ReportRequest;
import com.otterworks.report.model.ReportSchedule;
import com.otterworks.report.model.ReportType;
import com.otterworks.report.repository.ReportScheduleRepository;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;

import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.Date;

import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

@SpringBootTest
@ActiveProfiles("test")
class ReportSchedulePollerTest {

    @Autowired
    private ReportSchedulePoller poller;

    @Autowired
    private ReportScheduleRepository scheduleRepository;

    @Autowired
    private ObjectMapper objectMapper;

    @Test
    void pollCreatesReportAndAdvancesNextRunAt() throws Exception {
        // Create a schedule that is due (nextRunAt in the past)
        ReportRequest template = new ReportRequest();
        template.setReportName("Scheduled Usage Report");
        template.setCategory(ReportCategory.USAGE_ANALYTICS);
        template.setReportType(ReportType.CSV);
        template.setRequestedBy("scheduler");

        ReportSchedule schedule = new ReportSchedule();
        schedule.setName("Test Schedule");
        schedule.setCronExpression("0 0 * * * *"); // every hour
        schedule.setTimeZone("UTC");
        schedule.setTemplate(objectMapper.writeValueAsString(template));
        schedule.setRequestedBy("test-admin");
        schedule.setEnabled(true);
        schedule.setCreatedAt(new Date());
        schedule.setNextRunAt(Date.from(Instant.now().minus(1, ChronoUnit.HOURS)));

        schedule = scheduleRepository.save(schedule);
        Date originalNextRunAt = schedule.getNextRunAt();

        // Poll
        poller.pollSchedules();

        // Verify nextRunAt was advanced
        ReportSchedule updated = scheduleRepository.findById(schedule.getId()).orElseThrow();
        assertNotNull(updated.getLastRunAt(), "lastRunAt should be set");
        assertTrue(updated.getNextRunAt().after(originalNextRunAt), "nextRunAt should be advanced");
    }
}
