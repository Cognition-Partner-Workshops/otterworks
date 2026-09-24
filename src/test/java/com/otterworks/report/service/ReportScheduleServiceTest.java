package com.otterworks.report.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.otterworks.report.dto.ReportScheduleRequest;
import com.otterworks.report.dto.ReportScheduleResponse;
import com.otterworks.report.exception.InvalidScheduleException;
import com.otterworks.report.model.ReportCategory;
import com.otterworks.report.model.ReportRequest;
import com.otterworks.report.model.ReportSchedule;
import com.otterworks.report.model.ReportType;
import com.otterworks.report.repository.ReportScheduleRepository;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.junit.jupiter.api.Test;
import org.springframework.scheduling.support.CronExpression;

import java.time.Clock;
import java.time.Instant;
import java.time.ZoneId;
import java.time.ZoneOffset;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class ReportScheduleServiceTest {

    private static final Instant NOW = Instant.parse("2026-03-10T10:15:30Z");

    private final ReportScheduleRepository repository = mock(ReportScheduleRepository.class);
    private final ReportScheduleService service =
            new ReportScheduleService(repository, new ObjectMapper(), Clock.fixed(NOW, ZoneOffset.UTC));

    @ParameterizedTest
    @ValueSource(strings = {"0 0 2 * * *", "0 */15 * * * MON-FRI", "@hourly", "0 0 0 1 * ?", "0 0 9 * * MON#1"})
    void acceptsValidSpringCronExpressions(String cron) {
        assertEquals(CronExpression.parse(cron), ReportScheduleService.parseCron(cron));
    }

    @ParameterizedTest
    @ValueSource(strings = {"", "not a cron", "0 0 2 * *", "60 0 2 * * *", "0 0 25 * * *", "* * * * * * *", "0 0 2 * * MONDAYS"})
    void rejectsInvalidCronExpressions(String cron) {
        InvalidScheduleException ex = assertThrows(InvalidScheduleException.class,
                () -> ReportScheduleService.parseCron(cron));
        assertTrue(ex.getMessage().startsWith("Invalid cron expression"), ex.getMessage());
    }

    @Test
    void rejectsUnknownTimeZone() {
        assertThrows(InvalidScheduleException.class, () -> ReportScheduleService.parseZone("Atlantis/Nowhere"));
        assertEquals(ZoneId.of("Europe/Paris"), ReportScheduleService.parseZone("Europe/Paris"));
    }

    @Test
    void nextRunIsEvaluatedInTheScheduleTimeZone() {
        CronExpression daily2am = CronExpression.parse("0 0 2 * * *");

        Optional<Instant> utc = ReportScheduleService.nextRun(daily2am, ZoneId.of("UTC"), NOW);
        Optional<Instant> tokyo = ReportScheduleService.nextRun(daily2am, ZoneId.of("Asia/Tokyo"), NOW);

        assertEquals(Instant.parse("2026-03-11T02:00:00Z"), utc.orElseThrow());
        // 02:00 JST on 11 March is 17:00 UTC on 10 March.
        assertEquals(Instant.parse("2026-03-10T17:00:00Z"), tokyo.orElseThrow());
    }

    @Test
    void createComputesNextRunAndSerializesTemplate() {
        when(repository.save(any(ReportSchedule.class))).thenAnswer(inv -> inv.getArgument(0));
        ReportRequest template = new ReportRequest();
        template.setReportName("Weekly usage");
        template.setCategory(ReportCategory.USAGE_ANALYTICS);
        template.setReportType(ReportType.PDF);
        template.setRequestedBy("alice");

        ReportScheduleResponse response = service.create(
                new ReportScheduleRequest("weekly", "0 0 6 * * MON", null, template, null));

        assertEquals("UTC", response.timeZone());
        assertEquals("alice", response.requestedBy());
        assertTrue(response.enabled());
        assertEquals(NOW, response.createdAt());
        assertEquals(Instant.parse("2026-03-16T06:00:00Z"), response.nextRunAt());
        assertEquals("Weekly usage", response.template().getReportName());
        assertEquals(ReportType.PDF, response.template().getReportType());
    }

    @Test
    void createWithInvalidCronFailsBeforeSaving() {
        ReportRequest template = new ReportRequest();
        template.setRequestedBy("alice");

        assertThrows(InvalidScheduleException.class, () -> service.create(
                new ReportScheduleRequest("bad", "every day", "UTC", template, true)));
    }
}
