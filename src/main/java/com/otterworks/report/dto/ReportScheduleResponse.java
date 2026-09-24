package com.otterworks.report.dto;

import com.otterworks.report.model.ReportRequest;
import com.otterworks.report.model.ReportSchedule;
import io.swagger.v3.oas.annotations.media.Schema;

import java.time.Instant;

@Schema(description = "A recurring report schedule")
public record ReportScheduleResponse(
        Long id,
        String name,
        String cronExpression,
        String timeZone,
        ReportRequest template,
        String requestedBy,
        boolean enabled,
        Instant createdAt,
        Instant lastRunAt,
        Instant nextRunAt) {

    public static ReportScheduleResponse of(ReportSchedule schedule, ReportRequest template) {
        return new ReportScheduleResponse(
                schedule.getId(),
                schedule.getName(),
                schedule.getCronExpression(),
                schedule.getTimeZone(),
                template,
                schedule.getRequestedBy(),
                schedule.isEnabled(),
                schedule.getCreatedAt(),
                schedule.getLastRunAt(),
                schedule.getNextRunAt());
    }
}
