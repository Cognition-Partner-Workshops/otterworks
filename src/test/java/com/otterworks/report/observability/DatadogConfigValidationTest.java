package com.otterworks.report.observability;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

import java.io.File;
import java.util.HashSet;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class DatadogConfigValidationTest {

    private static final Set<String> KNOWN_METRICS = Set.of(
            "reports.generated",
            "reports.generation.duration",
            "reports.queue.depth",
            "cache.gets"
    );

    private final ObjectMapper objectMapper = new ObjectMapper();

    @Test
    void monitorsJsonIsValidAndReferencesKnownMetrics() throws Exception {
        File monitorsFile = new File("observability/datadog/monitors.json");
        assertTrue(monitorsFile.exists(), "monitors.json should exist");

        JsonNode monitors = objectMapper.readTree(monitorsFile);
        assertTrue(monitors.isArray(), "monitors.json should be a JSON array");
        assertTrue(monitors.size() >= 3, "Should have at least 3 monitors");

        Set<String> referencedMetrics = new HashSet<>();
        for (JsonNode monitor : monitors) {
            assertTrue(monitor.has("name"), "Each monitor should have a name");
            assertTrue(monitor.has("type"), "Each monitor should have a type");
            assertTrue(monitor.has("query"), "Each monitor should have a query");
            assertTrue(monitor.has("message"), "Each monitor should have a message");

            String query = monitor.get("query").asText();
            for (String metric : KNOWN_METRICS) {
                if (query.contains(metric)) {
                    referencedMetrics.add(metric);
                }
            }
        }
        assertFalse(referencedMetrics.isEmpty(), "Monitors should reference at least one known metric");
    }

    @Test
    void dashboardJsonIsValidAndReferencesKnownMetrics() throws Exception {
        File dashboardFile = new File("observability/datadog/dashboard.json");
        assertTrue(dashboardFile.exists(), "dashboard.json should exist");

        JsonNode dashboard = objectMapper.readTree(dashboardFile);
        assertTrue(dashboard.has("title"), "Dashboard should have a title");
        assertTrue(dashboard.has("widgets"), "Dashboard should have widgets");
        assertTrue(dashboard.get("widgets").isArray(), "Widgets should be an array");
        assertTrue(dashboard.get("widgets").size() >= 1, "Should have at least 1 widget");

        String dashboardStr = objectMapper.writeValueAsString(dashboard);
        Set<String> referencedMetrics = new HashSet<>();
        for (String metric : KNOWN_METRICS) {
            if (dashboardStr.contains(metric)) {
                referencedMetrics.add(metric);
            }
        }
        assertFalse(referencedMetrics.isEmpty(), "Dashboard should reference at least one known metric");
    }
}
