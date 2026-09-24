package com.otterworks.report.dto;

import com.otterworks.report.model.ReportRequest;
import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

@Schema(description = "Request to create a recurring report schedule")
public record ReportScheduleRequest(
        @NotBlank(message = "Schedule name is required")
        @Size(max = 200)
        @Schema(description = "Human-readable schedule name", requiredMode = Schema.RequiredMode.REQUIRED, example = "Nightly audit log")
        String name,

        @NotBlank(message = "Cron expression is required")
        @Size(max = 120)
        @Schema(description = "Spring cron expression (6 fields, seconds first)", requiredMode = Schema.RequiredMode.REQUIRED, example = "0 0 2 * * *")
        String cronExpression,

        @Schema(description = "IANA time zone the cron expression is evaluated in", defaultValue = "UTC", example = "Europe/London")
        String timeZone,

        @NotNull(message = "Report template is required")
        @Valid
        @Schema(description = "Report request created on every run", requiredMode = Schema.RequiredMode.REQUIRED)
        ReportRequest template,

        @Schema(description = "Whether the schedule is active", defaultValue = "true")
        Boolean enabled) {

    public String timeZoneOrDefault() {
        return timeZone == null || timeZone.isBlank() ? "UTC" : timeZone;
    }

    public boolean enabledOrDefault() {
        return enabled == null || enabled;
    }
}
