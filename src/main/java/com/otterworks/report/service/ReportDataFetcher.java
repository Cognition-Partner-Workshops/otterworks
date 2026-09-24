package com.otterworks.report.service;

import com.github.benmanes.caffeine.cache.Cache;
import com.github.benmanes.caffeine.cache.Caffeine;
import com.otterworks.report.config.AppConfig;
import com.otterworks.report.config.AsyncConfig;
import com.otterworks.report.config.ReportProperties;
import com.otterworks.report.util.ReportDateUtils;
import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.binder.cache.CaffeineCacheMetrics;
import org.apache.commons.lang3.StringUtils;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestTemplate;

import java.util.ArrayList;
import java.util.Collections;
import java.util.Date;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ExecutorService;
import java.util.function.Supplier;

/**
 * Fetches report data from the analytics, audit and auth services via REST.
 *
 * <p>Successful responses are cached in a Caffeine cache (bounded, TTL) exposed to Micrometer as
 * {@code cache.*} with tag {@code cache=report-data}. Upstream failures are never cached: the
 * fallback sample data is returned but the next call retries the upstream.
 */
@Service
public class ReportDataFetcher {

    private static final Logger logger = LoggerFactory.getLogger(ReportDataFetcher.class);

    public static final String CACHE_NAME = "report-data";

    private final RestTemplate restTemplate;
    private final AppConfig appConfig;
    private final ExecutorService fetchExecutor;
    private final Cache<String, List<Map<String, Object>>> dataCache;

    public ReportDataFetcher(RestTemplate restTemplate,
                             AppConfig appConfig,
                             ReportProperties properties,
                             MeterRegistry meterRegistry,
                             @Qualifier(AsyncConfig.FETCH_EXECUTOR) ExecutorService fetchExecutor) {
        this.restTemplate = restTemplate;
        this.appConfig = appConfig;
        this.fetchExecutor = fetchExecutor;
        this.dataCache = Caffeine.newBuilder()
                .maximumSize(properties.cache().maxSize())
                .expireAfterWrite(properties.cache().ttl())
                .recordStats()
                .build();
        CaffeineCacheMetrics.monitor(meterRegistry, dataCache, CACHE_NAME);
    }

    public List<Map<String, Object>> fetchAnalyticsData(Date dateFrom, Date dateTo, Map<String, String> parameters) {
        String metric = parameters != null ? parameters.get("metric") : null;
        String cacheKey = "analytics:" + rangeKey(dateFrom, dateTo) + (metric != null ? ":metric=" + metric : "");

        return cached(cacheKey, () -> {
            String url = appConfig.getAnalyticsServiceUrl() + "/api/v1/analytics/events"
                    + "?from=" + ReportDateUtils.toIsoString(dateFrom)
                    + "&to=" + ReportDateUtils.toIsoString(dateTo);
            if (StringUtils.isNotBlank(metric)) {
                url += "&metric=" + metric;
            }
            return fetchList(url, "events");
        }, () -> generateSampleAnalyticsData(dateFrom, dateTo));
    }

    public List<Map<String, Object>> fetchAuditData(Date dateFrom, Date dateTo, Map<String, String> parameters) {
        String cacheKey = "audit:" + rangeKey(dateFrom, dateTo);
        return cached(cacheKey, () -> fetchList(appConfig.getAuditServiceUrl() + "/api/v1/audit/events"
                + "?from=" + ReportDateUtils.toIsoString(dateFrom)
                + "&to=" + ReportDateUtils.toIsoString(dateTo), "events"),
                () -> generateSampleAuditData(dateFrom, dateTo));
    }

    public List<Map<String, Object>> fetchUserActivityData(Date dateFrom, Date dateTo, Map<String, String> parameters) {
        String cacheKey = "user-activity:" + rangeKey(dateFrom, dateTo);
        return cached(cacheKey, () -> fetchList(appConfig.getAuthServiceUrl() + "/api/v1/users/activity"
                + "?from=" + ReportDateUtils.toIsoString(dateFrom)
                + "&to=" + ReportDateUtils.toIsoString(dateTo), "activities"),
                () -> generateSampleUserActivityData(dateFrom, dateTo));
    }

    /**
     * Fetch analytics and audit data concurrently on the bounded fetch executor and return the
     * concatenation (analytics rows first). Used by report categories that combine both sources.
     */
    public List<Map<String, Object>> fetchAnalyticsAndAuditData(Date dateFrom, Date dateTo, Map<String, String> parameters) {
        CompletableFuture<List<Map<String, Object>>> analytics =
                CompletableFuture.supplyAsync(() -> fetchAnalyticsData(dateFrom, dateTo, parameters), fetchExecutor);
        CompletableFuture<List<Map<String, Object>>> audit =
                CompletableFuture.supplyAsync(() -> fetchAuditData(dateFrom, dateTo, parameters), fetchExecutor);
        List<Map<String, Object>> analyticsRows = analytics.join();
        List<Map<String, Object>> auditRows = audit.join();

        // The renderers take column headers from the first row, so give every row the union of keys.
        LinkedHashSet<String> columns = new LinkedHashSet<>();
        columns.add("source");
        analyticsRows.forEach(row -> columns.addAll(row.keySet()));
        auditRows.forEach(row -> columns.addAll(row.keySet()));

        List<Map<String, Object>> combined = new ArrayList<>(analyticsRows.size() + auditRows.size());
        analyticsRows.forEach(row -> combined.add(normalize(row, "analytics", columns)));
        auditRows.forEach(row -> combined.add(normalize(row, "audit", columns)));
        return combined;
    }

    private static Map<String, Object> normalize(Map<String, Object> row, String source, Set<String> columns) {
        Map<String, Object> out = new LinkedHashMap<>();
        for (String column : columns) {
            out.put(column, "source".equals(column) ? source : row.getOrDefault(column, ""));
        }
        return out;
    }

    /** Number of entries currently cached; exposed for tests and diagnostics. */
    public long cacheSize() {
        dataCache.cleanUp();
        return dataCache.estimatedSize();
    }

    private List<Map<String, Object>> cached(String key,
                                             Supplier<List<Map<String, Object>>> loader,
                                             Supplier<List<Map<String, Object>>> fallback) {
        List<Map<String, Object>> hit = dataCache.getIfPresent(key);
        if (hit != null) {
            return hit;
        }
        try {
            List<Map<String, Object>> loaded = loader.get();
            dataCache.put(key, loaded);
            return loaded;
        } catch (RestClientException e) {
            logger.error("Upstream fetch failed for {}, using sample data: {}", key, e.getMessage());
            return fallback.get();
        }
    }

    @SuppressWarnings("unchecked")
    private List<Map<String, Object>> fetchList(String url, String field) {
        logger.info("Fetching report data from: {}", url);
        ResponseEntity<Map> response = restTemplate.getForEntity(url, Map.class);
        Map<String, Object> body = response.getBody();
        if (body != null && body.get(field) instanceof List<?> rows) {
            return (List<Map<String, Object>>) rows;
        }
        return Collections.emptyList();
    }

    private static String rangeKey(Date dateFrom, Date dateTo) {
        return ReportDateUtils.toIsoString(dateFrom) + ":" + ReportDateUtils.toIsoString(dateTo);
    }

    // ----- Sample data generators for standalone/demo mode -----

    private List<Map<String, Object>> generateSampleAnalyticsData(Date dateFrom, Date dateTo) {
        List<Map<String, Object>> data = new ArrayList<>();
        String[] events = {"file_upload", "file_download", "doc_create", "doc_edit", "doc_share", "search_query"};
        String[] users = {"user-001", "user-002", "user-003", "user-004", "user-005"};

        for (int i = 0; i < 50; i++) {
            Map<String, Object> row = new HashMap<>();
            row.put("event_id", "evt-" + String.format("%04d", i));
            row.put("event_type", events[i % events.length]);
            row.put("user_id", users[i % users.length]);
            row.put("timestamp", ReportDateUtils.toIsoString(new Date(dateFrom.getTime() + (long) i * 3600000)));
            row.put("duration_ms", 100 + (i * 17) % 5000);
            row.put("status", i % 10 == 0 ? "error" : "success");
            row.put("metadata", "sample-analytics-row-" + i);
            data.add(row);
        }
        return data;
    }

    private List<Map<String, Object>> generateSampleAuditData(Date dateFrom, Date dateTo) {
        List<Map<String, Object>> data = new ArrayList<>();
        String[] actions = {"LOGIN", "LOGOUT", "FILE_ACCESS", "PERMISSION_CHANGE", "ADMIN_ACTION", "API_CALL"};
        String[] results = {"SUCCESS", "FAILURE", "DENIED"};

        for (int i = 0; i < 50; i++) {
            Map<String, Object> row = new HashMap<>();
            row.put("audit_id", "aud-" + String.format("%04d", i));
            row.put("action", actions[i % actions.length]);
            row.put("actor", "user-" + String.format("%03d", i % 10));
            row.put("result", results[i % results.length]);
            row.put("ip_address", "192.168.1." + (i % 255));
            row.put("timestamp", ReportDateUtils.toIsoString(new Date(dateFrom.getTime() + (long) i * 1800000)));
            row.put("resource", "/files/doc-" + (i % 20));
            row.put("details", "Audit entry " + i);
            data.add(row);
        }
        return data;
    }

    private List<Map<String, Object>> generateSampleUserActivityData(Date dateFrom, Date dateTo) {
        List<Map<String, Object>> data = new ArrayList<>();

        for (int i = 0; i < 25; i++) {
            Map<String, Object> row = new HashMap<>();
            row.put("user_id", "user-" + String.format("%03d", i));
            row.put("email", "user" + i + "@otterworks.example.com");
            row.put("last_login", ReportDateUtils.toIsoString(ReportDateUtils.daysAgo(i % 7)));
            row.put("files_uploaded", 10 + i * 3);
            row.put("docs_created", 5 + i * 2);
            row.put("storage_used_mb", 100 + i * 50);
            row.put("collaborations", i * 4);
            row.put("active", i % 5 != 0);
            data.add(row);
        }
        return data;
    }
}
