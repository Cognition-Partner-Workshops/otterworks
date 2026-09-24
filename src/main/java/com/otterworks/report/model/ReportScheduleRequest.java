package com.otterworks.report.model;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

@Schema(description = "Request to create a scheduled report")
public record ReportScheduleRequest(
        @NotBlank(message = "Name is required")
        @Schema(description = "Schedule name", requiredMode = Schema.RequiredMode.REQUIRED)
        String name,

        @NotBlank(message = "Cron expression is required")
        @Schema(description = "Cron expression (Spring 6-field format)", requiredMode = Schema.RequiredMode.REQUIRED, example = "0 0 8 * * MON-FRI")
        String cronExpression,

        @NotBlank(message = "Time zone is required")
        @Schema(description = "IANA time zone", requiredMode = Schema.RequiredMode.REQUIRED, example = "America/New_York")
        String timeZone,

        @NotNull(message = "Template is required")
        @Schema(description = "Report request template", requiredMode = Schema.RequiredMode.REQUIRED)
        ReportRequest template,

        @NotBlank(message = "Requester ID is required")
        @Schema(description = "User ID creating the schedule", requiredMode = Schema.RequiredMode.REQUIRED)
        String requestedBy
) {}
