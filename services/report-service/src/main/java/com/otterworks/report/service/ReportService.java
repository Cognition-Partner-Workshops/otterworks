package com.otterworks.report.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.otterworks.report.config.AppConfig;
import com.otterworks.report.model.Report;
import com.otterworks.report.model.ReportCategory;
import com.otterworks.report.model.ReportRequest;
import com.otterworks.report.model.ReportStatus;
import com.otterworks.report.repository.ReportRepository;
import com.otterworks.report.security.ReportCaller;
import com.otterworks.report.util.ReportDateUtils;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;

import javax.transaction.Transactional;
import java.io.File;
import java.util.Collections;
import java.util.Date;
import java.util.EnumSet;
import java.util.List;
import java.util.Optional;
import java.util.Set;
import java.util.stream.Collectors;

/**
 * Core report orchestration service.
 *
 * LEGACY PATTERNS:
 * - javax.transaction.Transactional (target: jakarta.transaction.Transactional
 *   or org.springframework.transaction.annotation.Transactional)
 * - java.util.Date throughout
 * - @Async delegated to ReportGenerationWorker (fire-and-forget, no error propagation)
 * - Manual JSON serialization for parameters
 * - Checked exceptions caught and rethrown as generic RuntimeException
 */
@Service
public class ReportService {

    private static final Logger logger = LoggerFactory.getLogger(ReportService.class);

    /** Categories that export platform audit events; only admins may create or read them. */
    private static final Set<ReportCategory> ADMIN_ONLY_CATEGORIES =
            Collections.unmodifiableSet(EnumSet.of(ReportCategory.AUDIT_LOG, ReportCategory.COMPLIANCE));

    private final ReportRepository reportRepository;
    private final ReportGenerationWorker generationWorker;
    private final AppConfig appConfig;
    private final ObjectMapper objectMapper;

    public ReportService(
            ReportRepository reportRepository,
            ReportGenerationWorker generationWorker,
            AppConfig appConfig) {
        this.reportRepository = reportRepository;
        this.generationWorker = generationWorker;
        this.appConfig = appConfig;
        this.objectMapper = new ObjectMapper();
    }

    /**
     * Whether the caller may create or read reports of this category.
     */
    public static boolean mayUseCategory(ReportCaller caller, ReportCategory category) {
        return !ADMIN_ONLY_CATEGORIES.contains(category) || caller.isAdmin();
    }

    /**
     * Create a new report request for the caller and start async generation.
     * The requester is always the caller; a requestedBy in the request body is ignored.
     */
    @Transactional
    public Report createReport(ReportRequest request, ReportCaller caller) {
        Report report = new Report();
        report.setReportName(request.getReportName());
        report.setCategory(request.getCategory());
        report.setReportType(request.getReportType());
        report.setRequestedBy(caller.getUserId());
        report.setStatus(ReportStatus.PENDING);
        report.setCreatedAt(new Date()); // LEGACY: new Date() instead of Instant.now()

        // Default date range: last 30 days
        report.setDateFrom(request.getDateFrom() != null ? request.getDateFrom() : ReportDateUtils.daysAgo(30));
        report.setDateTo(request.getDateTo() != null ? request.getDateTo() : new Date());

        // Serialize parameters
        if (request.getParameters() != null) {
            try {
                report.setParameters(objectMapper.writeValueAsString(request.getParameters()));
            } catch (JsonProcessingException e) {
                logger.warn("Failed to serialize report parameters: {}", e.getMessage());
            }
        }

        Report saved = reportRepository.save(report);
        logger.info("Created report request: id={}, name={}, type={}",
                saved.getId(), saved.getReportName(), saved.getReportType());

        // Defer async generation until after @Transactional commit so the worker thread
        // can see the persisted report (avoids race where findById returns empty).
        // LEGACY: TransactionSynchronization callback — modern approach uses @TransactionalEventListener.
        final Long reportId = saved.getId();
        TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization() {
            @Override
            public void afterCommit() {
                generationWorker.generateReportAsync(reportId);
            }
        });

        return saved;
    }

    /**
     * Get a report by ID if the caller requested it and may read its category.
     * Anyone else's report is indistinguishable from a missing one.
     */
    public Optional<Report> getReport(Long id, ReportCaller caller) {
        return reportRepository.findById(id).filter(report -> isVisibleTo(report, caller));
    }

    /**
     * List the caller's own reports.
     *
     * @param userId legacy filter; any user other than the caller has no reports visible to them
     * @param status optional status filter, ignored when userId is given (legacy behavior)
     */
    public List<Report> listReports(ReportCaller caller, String userId, ReportStatus status) {
        if (userId != null && !userId.equals(caller.getUserId())) {
            return Collections.emptyList();
        }
        List<Report> reports;
        if (userId != null) {
            reports = reportRepository.findByRequestedByOrderByCreatedAtDesc(caller.getUserId());
        } else {
            ReportStatus effective = status != null ? status : ReportStatus.COMPLETED;
            reports = reportRepository.findByRequestedByAndStatusOrderByCreatedAtAsc(caller.getUserId(), effective);
        }
        return reports.stream()
                .filter(report -> isVisibleTo(report, caller))
                .collect(Collectors.toList());
    }

    private static boolean isVisibleTo(Report report, ReportCaller caller) {
        return caller.getUserId().equals(report.getRequestedBy()) && mayUseCategory(caller, report.getCategory());
    }

    /**
     * Delete one of the caller's reports and its generated file.
     * File deletion is deferred to afterCommit to avoid inconsistency on rollback.
     */
    @Transactional
    public boolean deleteReport(Long id, ReportCaller caller) {
        Optional<Report> optReport = getReport(id, caller);
        if (!optReport.isPresent()) {
            return false;
        }

        Report report = optReport.get();
        final String filePath = report.getFilePath();

        // Delete DB record first
        reportRepository.deleteById(id);
        logger.info("Deleted report: {}", id);

        // Defer file deletion until after transaction commits so a rollback
        // doesn't leave the DB record pointing to a missing file.
        if (filePath != null) {
            TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization() {
                @Override
                public void afterCommit() {
                    File file = new File(filePath);
                    if (file.exists()) {
                        boolean deleted = file.delete();
                        if (!deleted) {
                            logger.warn("Failed to delete report file: {}", filePath);
                        }
                    }
                }
            });
        }

        return true;
    }

}
