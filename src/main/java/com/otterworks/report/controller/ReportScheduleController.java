package com.otterworks.report.controller;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.otterworks.report.model.ReportRequest;
import com.otterworks.report.model.ReportSchedule;
import com.otterworks.report.model.ReportScheduleRequest;
import com.otterworks.report.model.ReportScheduleResponse;
import com.otterworks.report.repository.ReportScheduleRepository;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.responses.ApiResponse;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.http.ProblemDetail;
import org.springframework.http.ResponseEntity;
import org.springframework.scheduling.support.CronExpression;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.net.URI;
import java.time.LocalDateTime;
import java.time.ZoneId;
import java.util.Date;
import java.util.List;
import java.util.Optional;

@RestController
@RequestMapping("/api/v1/reports/schedules")
@Tag(name = "Report Schedules", description = "Scheduled (recurring) report management")
public class ReportScheduleController {

    private final ReportScheduleRepository scheduleRepository;
    private final ObjectMapper objectMapper;

    public ReportScheduleController(ReportScheduleRepository scheduleRepository, ObjectMapper objectMapper) {
        this.scheduleRepository = scheduleRepository;
        this.objectMapper = objectMapper;
    }

    @PostMapping
    @Operation(summary = "Create a report schedule")
    @ApiResponses({
            @ApiResponse(responseCode = "201", description = "Schedule created"),
            @ApiResponse(responseCode = "400", description = "Invalid cron expression or missing fields")
    })
    public ResponseEntity<?> createSchedule(@Valid @RequestBody ReportScheduleRequest request) {
        // Validate cron expression
        if (!CronExpression.isValidExpression(request.cronExpression())) {
            ProblemDetail problem = ProblemDetail.forStatusAndDetail(
                    HttpStatus.BAD_REQUEST, "Invalid cron expression: " + request.cronExpression());
            problem.setTitle("Bad Request");
            problem.setType(URI.create("about:blank"));
            return ResponseEntity.badRequest().body(problem);
        }

        // Validate time zone
        try {
            ZoneId.of(request.timeZone());
        } catch (Exception e) {
            ProblemDetail problem = ProblemDetail.forStatusAndDetail(
                    HttpStatus.BAD_REQUEST, "Invalid time zone: " + request.timeZone());
            problem.setTitle("Bad Request");
            problem.setType(URI.create("about:blank"));
            return ResponseEntity.badRequest().body(problem);
        }

        try {
            ReportSchedule schedule = new ReportSchedule();
            schedule.setName(request.name());
            schedule.setCronExpression(request.cronExpression());
            schedule.setTimeZone(request.timeZone());
            schedule.setTemplate(objectMapper.writeValueAsString(request.template()));
            schedule.setRequestedBy(request.requestedBy());
            schedule.setEnabled(true);
            schedule.setCreatedAt(new Date());

            // Compute next run
            CronExpression cron = CronExpression.parse(request.cronExpression());
            LocalDateTime next = cron.next(LocalDateTime.now(ZoneId.of(request.timeZone())));
            if (next != null) {
                schedule.setNextRunAt(Date.from(next.atZone(ZoneId.of(request.timeZone())).toInstant()));
            }

            ReportSchedule saved = scheduleRepository.save(schedule);
            ReportRequest template = objectMapper.readValue(saved.getTemplate(), ReportRequest.class);
            return ResponseEntity.status(HttpStatus.CREATED)
                    .body(ReportScheduleResponse.fromEntity(saved, template));
        } catch (JsonProcessingException e) {
            ProblemDetail problem = ProblemDetail.forStatusAndDetail(
                    HttpStatus.BAD_REQUEST, "Invalid template: " + e.getMessage());
            problem.setTitle("Bad Request");
            problem.setType(URI.create("about:blank"));
            return ResponseEntity.badRequest().body(problem);
        }
    }

    @GetMapping
    @Operation(summary = "List all report schedules")
    public ResponseEntity<List<ReportScheduleResponse>> listSchedules() {
        List<ReportScheduleResponse> responses = scheduleRepository.findAll().stream()
                .map(this::toResponse)
                .toList();
        return ResponseEntity.ok(responses);
    }

    @GetMapping("/{id}")
    @Operation(summary = "Get a report schedule by ID")
    @ApiResponses({
            @ApiResponse(responseCode = "200", description = "Schedule found"),
            @ApiResponse(responseCode = "404", description = "Schedule not found")
    })
    public ResponseEntity<?> getSchedule(@PathVariable Long id) {
        Optional<ReportSchedule> opt = scheduleRepository.findById(id);
        if (opt.isEmpty()) {
            ProblemDetail problem = ProblemDetail.forStatusAndDetail(
                    HttpStatus.NOT_FOUND, "Schedule not found: " + id);
            problem.setTitle("Not Found");
            problem.setType(URI.create("about:blank"));
            return ResponseEntity.status(HttpStatus.NOT_FOUND).body(problem);
        }
        return ResponseEntity.ok(toResponse(opt.get()));
    }

    @DeleteMapping("/{id}")
    @Operation(summary = "Delete a report schedule")
    @ApiResponses({
            @ApiResponse(responseCode = "204", description = "Schedule deleted"),
            @ApiResponse(responseCode = "404", description = "Schedule not found")
    })
    public ResponseEntity<?> deleteSchedule(@PathVariable Long id) {
        if (!scheduleRepository.existsById(id)) {
            ProblemDetail problem = ProblemDetail.forStatusAndDetail(
                    HttpStatus.NOT_FOUND, "Schedule not found: " + id);
            problem.setTitle("Not Found");
            problem.setType(URI.create("about:blank"));
            return ResponseEntity.status(HttpStatus.NOT_FOUND).body(problem);
        }
        scheduleRepository.deleteById(id);
        return ResponseEntity.noContent().build();
    }

    private ReportScheduleResponse toResponse(ReportSchedule schedule) {
        try {
            ReportRequest template = objectMapper.readValue(schedule.getTemplate(), ReportRequest.class);
            return ReportScheduleResponse.fromEntity(schedule, template);
        } catch (JsonProcessingException e) {
            return ReportScheduleResponse.fromEntity(schedule, null);
        }
    }
}
