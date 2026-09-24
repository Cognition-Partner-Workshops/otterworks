package com.otterworks.report.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.otterworks.report.config.AppConfig;
import com.otterworks.report.model.Report;
import com.otterworks.report.model.ReportCategory;
import com.otterworks.report.model.ReportStatus;
import com.otterworks.report.model.ReportType;
import com.otterworks.report.repository.ReportRepository;
import com.otterworks.report.util.ReportDateUtils;
import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.Timer;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Component;

import java.io.File;
import java.util.ArrayList;
import java.util.Date;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.Executor;

/**
 * Separate bean for async report generation.
 *
 * LEGACY PATTERNS (intentional tech debt):
 * - Extracted to separate bean to work around Spring AOP self-invocation limitation
 * - Still uses java.util.Date, fire-and-forget @Async, checked-to-unchecked exception wrapping
 *
 * NOTE: @Async requires the call to come from a different Spring bean (external invocation)
 * so the proxy can intercept and run the method on the async executor thread pool.
 */
@Component
public class ReportGenerationWorker {

    private static final Logger logger = LoggerFactory.getLogger(ReportGenerationWorker.class);

    private final ReportRepository reportRepository;
    private final ReportDataFetcher dataFetcher;
    private final PdfReportGenerator pdfGenerator;
    private final CsvReportGenerator csvGenerator;
    private final ExcelReportGenerator excelGenerator;
    private final AppConfig appConfig;
    private final ObjectMapper objectMapper;
    private final MeterRegistry meterRegistry;
    private final Executor reportGenerationExecutor;

    public ReportGenerationWorker(
            ReportRepository reportRepository,
            ReportDataFetcher dataFetcher,
            PdfReportGenerator pdfGenerator,
            CsvReportGenerator csvGenerator,
            ExcelReportGenerator excelGenerator,
            AppConfig appConfig,
            MeterRegistry meterRegistry,
            Executor reportGenerationExecutor) {
        this.reportRepository = reportRepository;
        this.dataFetcher = dataFetcher;
        this.pdfGenerator = pdfGenerator;
        this.csvGenerator = csvGenerator;
        this.excelGenerator = excelGenerator;
        this.appConfig = appConfig;
        this.objectMapper = new ObjectMapper();
        this.meterRegistry = meterRegistry;
        this.reportGenerationExecutor = reportGenerationExecutor;
    }

    /**
     * Async report generation — runs in background thread pool.
     */
    @Async("reportGenerationExecutor")
    @SuppressWarnings("unchecked")
    public void generateReportAsync(Long reportId) {
        Optional<Report> optReport = reportRepository.findById(reportId);
        if (!optReport.isPresent()) { // LEGACY: !isPresent() instead of isEmpty() (Java 11+)
            logger.error("Report not found for generation: {}", reportId);
            return;
        }

        Report report = optReport.get();
        report.setStatus(ReportStatus.GENERATING);
        reportRepository.save(report);

        Timer.Sample timerSample = Timer.start(meterRegistry);
        String reportType = report.getReportType() != null ? report.getReportType().name() : "UNKNOWN";
        String category = report.getCategory() != null ? report.getCategory().name() : "UNKNOWN";

        try {
            // Parse parameters
            Map<String, String> params = null;
            if (report.getParameters() != null) {
                params = objectMapper.readValue(report.getParameters(), Map.class);
            }

            // Fetch data based on category — parallel for categories needing multiple sources
            List<Map<String, Object>> data = fetchDataForCategory(
                    report.getCategory(), report.getDateFrom(), report.getDateTo(), params);

            // Cap at max rows
            if (data.size() > appConfig.getMaxRows()) {
                data = data.subList(0, appConfig.getMaxRows());
                logger.warn("Report {} truncated to {} rows", reportId, appConfig.getMaxRows());
            }

            // Generate report file
            File outputFile = generateFile(report, data);

            // Update report record
            report.setStatus(ReportStatus.COMPLETED);
            report.setCompletedAt(new Date());
            report.setFilePath(outputFile.getAbsolutePath());
            report.setFileSizeBytes(outputFile.length());
            report.setRowCount(data.size());
            reportRepository.save(report);

            String duration = ReportDateUtils.humanReadableDuration(report.getCreatedAt(), report.getCompletedAt());
            logger.info("Report {} completed: {} rows, {} bytes, took {}",
                    reportId, data.size(), outputFile.length(), duration);

            // Record success metrics
            timerSample.stop(Timer.builder("reports.generation.duration")
                    .tag("report_type", reportType)
                    .tag("format", category)
                    .register(meterRegistry));
            Counter.builder("reports.generated")
                    .tag("report_type", category)
                    .tag("format", reportType)
                    .tag("outcome", "success")
                    .register(meterRegistry)
                    .increment();

        } catch (Exception e) {
            logger.error("Report generation failed for {}: {}", reportId, e.getMessage(), e);
            report.setStatus(ReportStatus.FAILED);
            report.setCompletedAt(new Date());
            report.setErrorMessage(e.getMessage());
            reportRepository.save(report);

            // Record failure metrics
            timerSample.stop(Timer.builder("reports.generation.duration")
                    .tag("report_type", reportType)
                    .tag("format", category)
                    .register(meterRegistry));
            Counter.builder("reports.generated")
                    .tag("report_type", category)
                    .tag("format", reportType)
                    .tag("outcome", "failure")
                    .register(meterRegistry)
                    .increment();
        }
    }

    private List<Map<String, Object>> fetchDataForCategory(
            ReportCategory category, Date dateFrom, Date dateTo, Map<String, String> params) {

        switch (category) {
            case COMPLIANCE: {
                // Compliance needs both analytics and audit — fetch in parallel
                CompletableFuture<List<Map<String, Object>>> analyticsFuture =
                        CompletableFuture.supplyAsync(() -> dataFetcher.fetchAnalyticsData(dateFrom, dateTo, params), reportGenerationExecutor);
                CompletableFuture<List<Map<String, Object>>> auditFuture =
                        CompletableFuture.supplyAsync(() -> dataFetcher.fetchAuditData(dateFrom, dateTo, params), reportGenerationExecutor);
                List<Map<String, Object>> combined = new ArrayList<>();
                combined.addAll(analyticsFuture.join());
                combined.addAll(auditFuture.join());
                return combined;
            }
            case USAGE_ANALYTICS:
            case COLLABORATION_METRICS:
            case SYSTEM_HEALTH:
                return dataFetcher.fetchAnalyticsData(dateFrom, dateTo, params);
            case AUDIT_LOG:
                return dataFetcher.fetchAuditData(dateFrom, dateTo, params);
            case USER_ACTIVITY:
            case STORAGE_SUMMARY:
                return dataFetcher.fetchUserActivityData(dateFrom, dateTo, params);
            default:
                logger.warn("Unknown category: {}, defaulting to analytics", category);
                return dataFetcher.fetchAnalyticsData(dateFrom, dateTo, params);
        }
    }

    private File generateFile(Report report, List<Map<String, Object>> data) throws Exception {
        String outputDir = appConfig.getReportOutputDir();

        switch (report.getReportType()) {
            case PDF:
                return pdfGenerator.generatePdf(report, data, outputDir);
            case CSV:
                return csvGenerator.generateCsv(report, data, outputDir);
            case EXCEL:
                return excelGenerator.generateExcel(report, data, outputDir);
            default:
                throw new IllegalArgumentException("Unsupported report type: " + report.getReportType());
        }
    }
}
