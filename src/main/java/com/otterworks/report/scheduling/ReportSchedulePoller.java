package com.otterworks.report.scheduling;

import com.otterworks.report.model.Report;
import com.otterworks.report.model.ReportRequest;
import com.otterworks.report.model.ReportSchedule;
import com.otterworks.report.repository.ReportScheduleRepository;
import com.otterworks.report.service.ReportScheduleService;
import com.otterworks.report.service.ReportService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.scheduling.support.CronExpression;
import org.springframework.stereotype.Component;

import java.time.Clock;
import java.time.Instant;
import java.time.ZoneId;
import java.time.temporal.ChronoUnit;
import java.util.List;

/**
 * Polls for due {@link ReportSchedule}s and creates a report for each one.
 *
 * <p>Multi-instance safety: a run is first <em>claimed</em> with a conditional UPDATE that only
 * succeeds if the row still has the version and {@code nextRunAt} this instance read. Two instances
 * polling at the same moment both read the same row, but only one UPDATE matches; the loser skips the
 * schedule. The claim runs in its own transaction and commits before the report is created, so a
 * failure while creating the report does not roll the schedule back into a due state (that would make
 * a permanently failing template fire on every poll).
 */
@Component
public class ReportSchedulePoller {

    private static final Logger logger = LoggerFactory.getLogger(ReportSchedulePoller.class);

    private final ReportScheduleRepository repository;
    private final ReportScheduleService scheduleService;
    private final ReportService reportService;
    private final Clock clock;

    public ReportSchedulePoller(ReportScheduleRepository repository,
                                ReportScheduleService scheduleService,
                                ReportService reportService,
                                Clock clock) {
        this.repository = repository;
        this.scheduleService = scheduleService;
        this.reportService = reportService;
        this.clock = clock;
    }

    @Scheduled(fixedDelayString = "${otterworks.report.schedule.poll-interval:60s}",
            initialDelayString = "${otterworks.report.schedule.initial-delay:10s}")
    public void poll() {
        Instant now = clock.instant();
        List<ReportSchedule> due = repository.findByEnabledTrueAndNextRunAtLessThanEqual(now);
        if (due.isEmpty()) {
            return;
        }
        logger.debug("{} report schedule(s) due at {}", due.size(), now);
        for (ReportSchedule schedule : due) {
            try {
                runIfClaimed(schedule, now);
            } catch (RuntimeException e) {
                logger.error("Schedule {} ({}) failed: {}", schedule.getId(), schedule.getName(), e.getMessage(), e);
            }
        }
    }

    /** Returns the created report, or {@code null} when another instance claimed this run first. */
    public Report runIfClaimed(ReportSchedule schedule, Instant now) {
        CronExpression cron = ReportScheduleService.parseCron(schedule.getCronExpression());
        ZoneId zone = ZoneId.of(schedule.getTimeZone());
        // Advance from "now" rather than from the missed nextRunAt so a long outage yields one
        // catch-up run instead of a burst.
        // A cron that never fires again is parked far in the future rather than at Instant.MAX,
        // which does not fit a SQL timestamp.
        Instant next = ReportScheduleService.nextRun(cron, zone, now)
                .orElse(now.plus(36500, ChronoUnit.DAYS));

        int claimed = repository.claimRun(schedule.getId(), schedule.getVersion(), schedule.getNextRunAt(), now, next);
        if (claimed == 0) {
            logger.debug("Schedule {} already claimed by another instance", schedule.getId());
            return null;
        }

        ReportRequest template = scheduleService.templateOf(schedule);
        Report report = reportService.createReport(template);
        logger.info("Schedule {} ({}) created report {}; next run at {}",
                schedule.getId(), schedule.getName(), report.getId(), next);
        return report;
    }
}
