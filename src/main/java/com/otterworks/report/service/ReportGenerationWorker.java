package com.otterworks.report.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.otterworks.report.config.AppConfig;
import com.otterworks.report.config.AsyncConfig;
import com.otterworks.report.metrics.ReportMetrics;
import com.otterworks.report.model.Report;
import com.otterworks.report.model.ReportCategory;
import com.otterworks.report.model.ReportStatus;
import com.otterworks.report.model.ReportType;
import com.otterworks.report.repository.ReportRepository;
import com.otterworks.report.util.ReportDateUtils;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.slf4j.MDC;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Component;

import java.io.File;
import java.time.Duration;
import java.util.Date;
import java.util.List;
import java.util.Map;
import java.util.Optional;

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
    private final ReportMetrics metrics;
    private final ObjectMapper objectMapper;

    public ReportGenerationWorker(
            ReportRepository reportRepository,
            ReportDataFetcher dataFetcher,
            PdfReportGenerator pdfGenerator,
            CsvReportGenerator csvGenerator,
            ExcelReportGenerator excelGenerator,
            AppConfig appConfig,
            ReportMetrics metrics) {
        this.reportRepository = reportRepository;
        this.dataFetcher = dataFetcher;
        this.pdfGenerator = pdfGenerator;
        this.csvGenerator = csvGenerator;
        this.excelGenerator = excelGenerator;
        this.appConfig = appConfig;
        this.metrics = metrics;
        this.objectMapper = new ObjectMapper();
    }

    /**
     * Async report generation — runs in background thread pool.
     *
     * LEGACY: @Async with no return type (fire-and-forget).
     * Modern approach: return CompletableFuture<Void> or use reactive pipeline.
     */
    @Async(AsyncConfig.REPORT_GENERATION_EXECUTOR)
    public void generateReportAsync(Long reportId) {
        MDC.put("reportId", String.valueOf(reportId));
        try {
            generateReport(reportId);
        } finally {
            MDC.remove("reportId");
        }
    }

    @SuppressWarnings("unchecked")
    void generateReport(Long reportId) {
        Optional<Report> optReport = reportRepository.findById(reportId);
        if (optReport.isEmpty()) {
            logger.error("Report not found for generation: {}", reportId);
            return;
        }

        Report report = optReport.get();
        report.setStatus(ReportStatus.GENERATING);
        reportRepository.save(report);

        long startNanos = System.nanoTime();
        try {
            // Parse parameters
            Map<String, String> params = null;
            if (report.getParameters() != null) {
                params = objectMapper.readValue(report.getParameters(), Map.class);
            }

            // Fetch data based on category
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

            metrics.recordGenerated(report.getCategory(), report.getReportType(), ReportMetrics.Outcome.SUCCESS);
            String duration = ReportDateUtils.humanReadableDuration(report.getCreatedAt(), report.getCompletedAt());
            logger.info("Report {} completed: {} rows, {} bytes, took {}",
                    reportId, data.size(), outputFile.length(), duration);

        } catch (Exception e) {
            logger.error("Report generation failed for {}: {}", reportId, e.getMessage(), e);
            report.setStatus(ReportStatus.FAILED);
            report.setCompletedAt(new Date());
            report.setErrorMessage(e.getMessage());
            reportRepository.save(report);
            metrics.recordGenerated(report.getCategory(), report.getReportType(), ReportMetrics.Outcome.FAILURE);
        } finally {
            metrics.recordDuration(report.getCategory(), report.getReportType(),
                    Duration.ofNanos(System.nanoTime() - startNanos));
        }
    }

    private List<Map<String, Object>> fetchDataForCategory(
            ReportCategory category, Date dateFrom, Date dateTo, Map<String, String> params) {

        return switch (category) {
            case USAGE_ANALYTICS, COLLABORATION_METRICS, SYSTEM_HEALTH ->
                    dataFetcher.fetchAnalyticsData(dateFrom, dateTo, params);
            case AUDIT_LOG -> dataFetcher.fetchAuditData(dateFrom, dateTo, params);
            // Compliance reports combine usage evidence with the audit trail: both sources, fetched in parallel.
            case COMPLIANCE -> dataFetcher.fetchAnalyticsAndAuditData(dateFrom, dateTo, params);
            case USER_ACTIVITY, STORAGE_SUMMARY -> dataFetcher.fetchUserActivityData(dateFrom, dateTo, params);
        };
    }

    private File generateFile(Report report, List<Map<String, Object>> data) throws Exception {
        String outputDir = appConfig.getReportOutputDir();

        return switch (report.getReportType()) {
            case PDF -> pdfGenerator.generatePdf(report, data, outputDir);
            case CSV -> csvGenerator.generateCsv(report, data, outputDir);
            case EXCEL -> excelGenerator.generateExcel(report, data, outputDir);
        };
    }
}
