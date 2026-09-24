package com.otterworks.report.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.otterworks.report.model.ReportRequest;
import com.otterworks.report.model.ReportSchedule;
import com.otterworks.report.repository.ReportScheduleRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.orm.ObjectOptimisticLockingFailureException;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.scheduling.support.CronExpression;
import org.springframework.stereotype.Component;

import java.time.LocalDateTime;
import java.time.ZoneId;
import java.util.Date;
import java.util.List;

@Component
public class ReportSchedulePoller {

    private static final Logger logger = LoggerFactory.getLogger(ReportSchedulePoller.class);

    private final ReportScheduleRepository scheduleRepository;
    private final ReportService reportService;
    private final ObjectMapper objectMapper;

    public ReportSchedulePoller(ReportScheduleRepository scheduleRepository,
                                ReportService reportService,
                                ObjectMapper objectMapper) {
        this.scheduleRepository = scheduleRepository;
        this.reportService = reportService;
        this.objectMapper = objectMapper;
    }

    @Scheduled(fixedDelayString = "${otterworks.report.schedule.poll-interval:60000}")
    public void pollSchedules() {
        List<ReportSchedule> due = scheduleRepository.findByEnabledTrueAndNextRunAtLessThanEqual(new Date());
        for (ReportSchedule schedule : due) {
            try {
                processSchedule(schedule);
            } catch (ObjectOptimisticLockingFailureException e) {
                logger.info("Schedule {} already picked up by another instance, skipping", schedule.getId());
            } catch (Exception e) {
                logger.error("Failed to process schedule {}: {}", schedule.getId(), e.getMessage(), e);
            }
        }
    }

    private void processSchedule(ReportSchedule schedule) throws Exception {
        ReportRequest template = objectMapper.readValue(schedule.getTemplate(), ReportRequest.class);
        reportService.createReport(template);

        schedule.setLastRunAt(new Date());

        // Advance nextRunAt
        CronExpression cron = CronExpression.parse(schedule.getCronExpression());
        ZoneId zone = ZoneId.of(schedule.getTimeZone());
        LocalDateTime next = cron.next(LocalDateTime.now(zone));
        if (next != null) {
            schedule.setNextRunAt(Date.from(next.atZone(zone).toInstant()));
        }

        scheduleRepository.save(schedule); // optimistic lock protects against double-run
        logger.info("Executed schedule {} ({}), next run at {}", schedule.getId(), schedule.getName(), schedule.getNextRunAt());
    }
}
