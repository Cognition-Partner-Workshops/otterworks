package com.otterworks.report.service;

import com.otterworks.report.config.AppConfig;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import org.junit.jupiter.api.Test;
import org.springframework.http.ResponseEntity;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestTemplate;

import java.util.Date;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class ReportDataFetcherCacheTest {

    @Test
    void secondIdenticalFetchDoesNotCallRestTemplate() {
        RestTemplate restTemplate = mock(RestTemplate.class);
        AppConfig appConfig = mock(AppConfig.class);
        when(appConfig.getAnalyticsServiceUrl()).thenReturn("http://analytics:8088");

        // Simulate a failed REST call so sample data is used via the catch-block fallback
        when(restTemplate.getForEntity(anyString(), eq(Map.class)))
                .thenThrow(new RestClientException("Connection refused"));

        ReportDataFetcher fetcher = new ReportDataFetcher(restTemplate, appConfig, new SimpleMeterRegistry());

        Date from = new Date(1000000000000L);
        Date to = new Date(1000000100000L);

        // First call — should attempt REST then fall back to sample data
        List<Map<String, Object>> result1 = fetcher.fetchAnalyticsData(from, to, null);

        // Second call with same parameters — cache miss generated sample data on first call,
        // but for the Caffeine cache version the RestTemplate call should NOT happen on cache hits.
        // Since first call threw and fell back, the cache won't have an entry.
        // So let's use a scenario where REST succeeds:
        // Reset and test with a successful call
        RestTemplate restTemplate2 = mock(RestTemplate.class);
        AppConfig appConfig2 = mock(AppConfig.class);
        when(appConfig2.getAnalyticsServiceUrl()).thenReturn("http://analytics:8088");
        when(appConfig2.getAuthServiceUrl()).thenReturn("http://auth:8081");

        @SuppressWarnings("unchecked")
        ResponseEntity<Map> mockResponse = mock(ResponseEntity.class);
        Map<String, Object> body = Map.of("events", List.of(Map.of("id", "1")));
        when(mockResponse.getBody()).thenReturn(body);
        when(restTemplate2.getForEntity(anyString(), eq(Map.class))).thenReturn(mockResponse);

        ReportDataFetcher fetcher2 = new ReportDataFetcher(restTemplate2, appConfig2, new SimpleMeterRegistry());

        List<Map<String, Object>> first = fetcher2.fetchAnalyticsData(from, to, null);
        assertEquals(1, first.size());

        // Second identical call — should come from cache, no REST call
        List<Map<String, Object>> second = fetcher2.fetchAnalyticsData(from, to, null);
        assertEquals(1, second.size());

        // RestTemplate should have been called only once
        verify(restTemplate2, times(1)).getForEntity(anyString(), eq(Map.class));
    }
}
