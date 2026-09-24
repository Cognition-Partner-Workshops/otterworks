package com.otterworks.report.model;

import io.swagger.v3.oas.annotations.media.Schema;

import java.util.Date;

@Schema(description = "Scheduled report response")
public record ReportScheduleResponse(
        Long id,
        String name,
        String cronExpression,
        String timeZone,
        ReportRequest template,
        String requestedBy,
        boolean enabled,
        Date createdAt,
        Date lastRunAt,
        Date nextRunAt
) {
    public static ReportScheduleResponse fromEntity(ReportSchedule entity, ReportRequest template) {
        return new ReportScheduleResponse(
                entity.getId(),
                entity.getName(),
                entity.getCronExpression(),
                entity.getTimeZone(),
                template,
                entity.getRequestedBy(),
                entity.isEnabled(),
                entity.getCreatedAt(),
                entity.getLastRunAt(),
                entity.getNextRunAt()
        );
    }
}
