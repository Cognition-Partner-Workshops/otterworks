package com.otterworks.report.service;

import com.otterworks.report.config.AppConfig;
import com.otterworks.report.config.ReportProperties;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.ResponseEntity;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestTemplate;

import java.time.Duration;
import java.util.Date;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.contains;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoMoreInteractions;
import static org.mockito.Mockito.when;

class ReportDataFetcherCacheTest {

    private static final Date FROM = new Date(1_700_000_000_000L);
    private static final Date TO = new Date(1_700_086_400_000L);

    private RestTemplate restTemplate;
    private SimpleMeterRegistry registry;
    private ExecutorService executor;
    private ReportDataFetcher fetcher;

    @BeforeEach
    void setUp() {
        restTemplate = mock(RestTemplate.class);
        AppConfig appConfig = mock(AppConfig.class);
        when(appConfig.getAnalyticsServiceUrl()).thenReturn("http://analytics");
        when(appConfig.getAuditServiceUrl()).thenReturn("http://audit");
        when(appConfig.getAuthServiceUrl()).thenReturn("http://auth");

        ReportProperties properties = new ReportProperties(
                new ReportProperties.Cache(100, Duration.ofMinutes(5)),
                new ReportProperties.Executor(2, 2, 10),
                new ReportProperties.Fetch(2),
                new ReportProperties.Schedule(Duration.ofSeconds(60)));
        registry = new SimpleMeterRegistry();
        executor = Executors.newFixedThreadPool(2);
        fetcher = new ReportDataFetcher(restTemplate, appConfig, properties, registry, executor);
    }

    @AfterEach
    void tearDown() {
        executor.shutdownNow();
    }

    @Test
    void secondIdenticalAnalyticsFetchDoesNotCallUpstreamAgain() {
        List<Map<String, Object>> rows = List.of(Map.of("event_id", "evt-1"));
        when(restTemplate.getForEntity(anyString(), eq(Map.class)))
                .thenReturn(ResponseEntity.ok(Map.of("events", rows)));

        List<Map<String, Object>> first = fetcher.fetchAnalyticsData(FROM, TO, Map.of("metric", "uploads"));
        List<Map<String, Object>> second = fetcher.fetchAnalyticsData(FROM, TO, Map.of("metric", "uploads"));

        assertSame(first, second);
        verify(restTemplate, times(1)).getForEntity(contains("metric=uploads"), eq(Map.class));
        verifyNoMoreInteractions(restTemplate);

        assertEquals(1.0, registry.get("cache.gets").tag("cache", "report-data").tag("result", "hit").functionCounter().count());
        assertEquals(1.0, registry.get("cache.gets").tag("cache", "report-data").tag("result", "miss").functionCounter().count());
    }

    @Test
    void differentParametersAreDifferentCacheEntries() {
        when(restTemplate.getForEntity(anyString(), eq(Map.class)))
                .thenReturn(ResponseEntity.ok(Map.of("events", List.of())));

        fetcher.fetchAnalyticsData(FROM, TO, Map.of("metric", "a"));
        fetcher.fetchAnalyticsData(FROM, TO, Map.of("metric", "b"));
        fetcher.fetchAnalyticsData(FROM, TO, null);

        verify(restTemplate, times(3)).getForEntity(anyString(), eq(Map.class));
        assertEquals(3, fetcher.cacheSize());
    }

    @Test
    void userActivityFetchIsCached() {
        when(restTemplate.getForEntity(contains("/users/activity"), eq(Map.class)))
                .thenReturn(ResponseEntity.ok(Map.of("activities", List.of(Map.of("user_id", "u-1")))));

        fetcher.fetchUserActivityData(FROM, TO, null);
        fetcher.fetchUserActivityData(FROM, TO, null);
        fetcher.fetchUserActivityData(FROM, TO, Map.of("ignored", "param"));

        verify(restTemplate, times(1)).getForEntity(contains("/users/activity"), eq(Map.class));
    }

    @Test
    void upstreamFailureFallsBackToSampleDataAndIsNotCached() {
        when(restTemplate.getForEntity(anyString(), eq(Map.class)))
                .thenThrow(new ResourceAccessException("connection refused"));

        List<Map<String, Object>> first = fetcher.fetchAuditData(FROM, TO, null);
        List<Map<String, Object>> second = fetcher.fetchAuditData(FROM, TO, null);

        assertFalse(first.isEmpty(), "sample data returned on failure");
        assertFalse(second.isEmpty());
        verify(restTemplate, times(2)).getForEntity(anyString(), eq(Map.class));
        assertEquals(0, fetcher.cacheSize());
    }

    @Test
    void combinedFetchHitsBothSourcesOnceAndUnionsColumns() {
        when(restTemplate.getForEntity(contains("analytics"), eq(Map.class)))
                .thenReturn(ResponseEntity.ok(Map.of("events", List.of(Map.of("event_id", "e1")))));
        when(restTemplate.getForEntity(contains("audit"), eq(Map.class)))
                .thenReturn(ResponseEntity.ok(Map.of("events", List.of(Map.of("audit_id", "a1")))));

        List<Map<String, Object>> combined = fetcher.fetchAnalyticsAndAuditData(FROM, TO, null);
        fetcher.fetchAnalyticsAndAuditData(FROM, TO, null);

        assertEquals(2, combined.size());
        assertEquals(List.of("source", "event_id", "audit_id"), List.copyOf(combined.get(0).keySet()));
        assertEquals("analytics", combined.get(0).get("source"));
        assertEquals("audit", combined.get(1).get("source"));
        assertEquals("", combined.get(1).get("event_id"));
        verify(restTemplate, times(1)).getForEntity(contains("analytics"), eq(Map.class));
        verify(restTemplate, times(1)).getForEntity(contains("audit"), eq(Map.class));
        verify(restTemplate, never()).getForEntity(contains("auth"), eq(Map.class));
    }
}
