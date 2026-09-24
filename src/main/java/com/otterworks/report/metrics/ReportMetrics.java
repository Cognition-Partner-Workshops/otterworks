package com.otterworks.report.metrics;

import com.otterworks.report.model.ReportCategory;
import com.otterworks.report.model.ReportStatus;
import com.otterworks.report.model.ReportType;
import com.otterworks.report.repository.ReportRepository;
import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.Gauge;
import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.Timer;
import org.springframework.stereotype.Component;

import java.time.Duration;

/**
 * Business metrics for the report generation path.
 *
 * <ul>
 *   <li>{@value #GENERATED} — counter tagged report_type, format, outcome</li>
 *   <li>{@value #GENERATION_DURATION} — timer tagged report_type, format</li>
 *   <li>{@value #QUEUE_DEPTH} — gauge: reports PENDING or GENERATING</li>
 * </ul>
 *
 * {@code report_type} is the report category (what data is in it); {@code format} is the
 * output type (PDF/CSV/EXCEL).
 */
@Component
public class ReportMetrics {

    public static final String GENERATED = "reports.generated";
    public static final String GENERATION_DURATION = "reports.generation.duration";
    public static final String QUEUE_DEPTH = "reports.queue.depth";

    public static final String TAG_REPORT_TYPE = "report_type";
    public static final String TAG_FORMAT = "format";
    public static final String TAG_OUTCOME = "outcome";

    public enum Outcome {
        SUCCESS("success"), FAILURE("failure");

        private final String tagValue;

        Outcome(String tagValue) {
            this.tagValue = tagValue;
        }

        public String tagValue() {
            return tagValue;
        }
    }

    private final MeterRegistry registry;

    public ReportMetrics(MeterRegistry registry, ReportRepository reportRepository) {
        this.registry = registry;
        Gauge.builder(QUEUE_DEPTH, reportRepository,
                        repo -> repo.countByStatus(ReportStatus.PENDING) + repo.countByStatus(ReportStatus.GENERATING))
                .description("Reports waiting for or undergoing generation")
                .register(registry);
    }

    public void recordGenerated(ReportCategory category, ReportType format, Outcome outcome) {
        Counter.builder(GENERATED)
                .description("Report generation attempts by outcome")
                .tag(TAG_REPORT_TYPE, tag(category))
                .tag(TAG_FORMAT, tag(format))
                .tag(TAG_OUTCOME, outcome.tagValue())
                .register(registry)
                .increment();
    }

    public void recordDuration(ReportCategory category, ReportType format, Duration duration) {
        Timer.builder(GENERATION_DURATION)
                .description("End-to-end report generation time (fetch + render)")
                .publishPercentileHistogram()
                .tag(TAG_REPORT_TYPE, tag(category))
                .tag(TAG_FORMAT, tag(format))
                .register(registry)
                .record(duration);
    }

    private static String tag(Enum<?> value) {
        return value == null ? "unknown" : value.name().toLowerCase();
    }
}
