package com.otterworks.report.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.otterworks.report.dto.ReportScheduleRequest;
import com.otterworks.report.dto.ReportScheduleResponse;
import com.otterworks.report.exception.InvalidScheduleException;
import com.otterworks.report.exception.ScheduleNotFoundException;
import com.otterworks.report.model.ReportRequest;
import com.otterworks.report.model.ReportSchedule;
import com.otterworks.report.repository.ReportScheduleRepository;
import org.springframework.scheduling.support.CronExpression;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Clock;
import java.time.DateTimeException;
import java.time.Instant;
import java.time.ZoneId;
import java.time.ZonedDateTime;
import java.util.List;
import java.util.Optional;

@Service
public class ReportScheduleService {

    private final ReportScheduleRepository repository;
    private final ObjectMapper objectMapper;
    private final Clock clock;

    public ReportScheduleService(ReportScheduleRepository repository, ObjectMapper objectMapper, Clock clock) {
        this.repository = repository;
        this.objectMapper = objectMapper;
        this.clock = clock;
    }

    @Transactional
    public ReportScheduleResponse create(ReportScheduleRequest request) {
        CronExpression cron = parseCron(request.cronExpression());
        ZoneId zone = parseZone(request.timeZoneOrDefault());
        Instant now = clock.instant();

        ReportSchedule schedule = new ReportSchedule();
        schedule.setName(request.name());
        schedule.setCronExpression(request.cronExpression());
        schedule.setTimeZone(zone.getId());
        schedule.setTemplate(serialize(request.template()));
        schedule.setRequestedBy(request.template().getRequestedBy());
        schedule.setEnabled(request.enabledOrDefault());
        schedule.setCreatedAt(now);
        schedule.setNextRunAt(nextRun(cron, zone, now)
                .orElseThrow(() -> new InvalidScheduleException("Cron expression never fires: " + request.cronExpression())));

        return toResponse(repository.save(schedule));
    }

    @Transactional(readOnly = true)
    public List<ReportScheduleResponse> list() {
        return repository.findAll().stream().map(this::toResponse).toList();
    }

    @Transactional(readOnly = true)
    public ReportScheduleResponse get(Long id) {
        return repository.findById(id).map(this::toResponse).orElseThrow(() -> new ScheduleNotFoundException(id));
    }

    @Transactional
    public void delete(Long id) {
        if (!repository.existsById(id)) {
            throw new ScheduleNotFoundException(id);
        }
        repository.deleteById(id);
    }

    public ReportRequest templateOf(ReportSchedule schedule) {
        try {
            return objectMapper.readValue(schedule.getTemplate(), ReportRequest.class);
        } catch (JsonProcessingException e) {
            throw new IllegalStateException("Corrupt template on schedule " + schedule.getId(), e);
        }
    }

    /** Next fire time strictly after {@code from}, or empty when the expression never fires again. */
    public static Optional<Instant> nextRun(CronExpression cron, ZoneId zone, Instant from) {
        ZonedDateTime next = cron.next(from.atZone(zone));
        return Optional.ofNullable(next).map(ZonedDateTime::toInstant);
    }

    public static CronExpression parseCron(String expression) {
        try {
            return CronExpression.parse(expression);
        } catch (IllegalArgumentException e) {
            throw new InvalidScheduleException("Invalid cron expression '" + expression + "': " + e.getMessage());
        }
    }

    public static ZoneId parseZone(String zone) {
        try {
            return ZoneId.of(zone);
        } catch (DateTimeException e) {
            throw new InvalidScheduleException("Invalid time zone '" + zone + "'");
        }
    }

    private String serialize(ReportRequest template) {
        try {
            return objectMapper.writeValueAsString(template);
        } catch (JsonProcessingException e) {
            throw new InvalidScheduleException("Template is not serializable: " + e.getOriginalMessage());
        }
    }

    private ReportScheduleResponse toResponse(ReportSchedule schedule) {
        return ReportScheduleResponse.of(schedule, templateOf(schedule));
    }
}
