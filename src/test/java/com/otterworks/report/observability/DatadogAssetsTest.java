package com.otterworks.report.observability;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.otterworks.report.metrics.ReportMetrics;
import io.micrometer.core.instrument.Meter;
import io.micrometer.core.instrument.MeterRegistry;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;

import java.io.IOException;
import java.lang.reflect.Field;
import java.lang.reflect.Modifier;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;
import java.util.TreeSet;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Guards {@code observability/datadog/*.json}: both files must be valid Datadog API payloads and
 * every metric they query must be a metric this service actually emits.
 *
 * <p>"Emitted" means either a name declared as a constant on {@link ReportMetrics} or a meter that is
 * present in the live {@link MeterRegistry} after startup (Caffeine cache binder, executor binder,
 * JVM metrics, ...). Datadog's DogStatsD timer/histogram suffixes ({@code .95percentile},
 * {@code .median}, ...) are stripped before the lookup.
 */
@SpringBootTest
@ActiveProfiles("test")
class DatadogAssetsTest {

    private static final Path DATADOG_DIR = Path.of("observability", "datadog");
    private static final ObjectMapper JSON = new ObjectMapper();

    /** {@code <space aggregator>:<metric.name>{...}} inside a Datadog metric query. */
    private static final Pattern METRIC_QUERY = Pattern.compile("(?:sum|avg|min|max|count):([a-z][a-z0-9_.]*)\\{");
    private static final List<String> DOGSTATSD_SUFFIXES =
            List.of(".95percentile", ".median", ".avg", ".max", ".count", ".sum");
    private static final Set<String> MONITOR_TYPES = Set.of("metric alert", "query alert");

    @Autowired
    private MeterRegistry registry;

    @Test
    void monitorsAreValidDatadogMonitorPayloads() throws IOException {
        JsonNode monitors = JSON.readTree(DATADOG_DIR.resolve("monitors.json").toFile());
        assertTrue(monitors.isArray() && monitors.size() >= 3, "monitors.json is a non-empty array");

        Set<String> names = new LinkedHashSet<>();
        for (JsonNode monitor : monitors) {
            String name = requireText(monitor, "name");
            assertTrue(names.add(name), "duplicate monitor name: " + name);
            assertTrue(MONITOR_TYPES.contains(requireText(monitor, "type")), name + ": unsupported type");
            requireText(monitor, "query");
            requireText(monitor, "message");
            assertTrue(monitor.path("options").path("thresholds").has("critical"),
                    name + ": options.thresholds.critical is required");
            assertTrue(monitor.path("tags").isArray(), name + ": tags must be an array");
        }

        String joined = String.join("\n", names).toLowerCase();
        assertTrue(joined.contains("failure rate"), "a failure-rate monitor exists");
        assertTrue(joined.contains("p95"), "a p95 latency monitor exists");
        assertTrue(joined.contains("queue depth"), "a queue-depth monitor exists");
    }

    @Test
    void dashboardIsAValidDatadogDashboardPayload() throws IOException {
        JsonNode dashboard = JSON.readTree(DATADOG_DIR.resolve("dashboard.json").toFile());
        requireText(dashboard, "title");
        assertEquals("ordered", requireText(dashboard, "layout_type"));
        JsonNode widgets = dashboard.path("widgets");
        assertTrue(widgets.isArray() && widgets.size() > 0, "dashboard has widgets");
        widgets.forEach(DatadogAssetsTest::assertWidgetShape);
    }

    @Test
    void everyReferencedMetricExistsInTheCode() throws IOException {
        Set<String> referenced = new TreeSet<>();
        referenced.addAll(metricNamesIn(DATADOG_DIR.resolve("monitors.json")));
        referenced.addAll(metricNamesIn(DATADOG_DIR.resolve("dashboard.json")));
        assertTrue(referenced.containsAll(List.of(
                        ReportMetrics.GENERATED, ReportMetrics.GENERATION_DURATION, ReportMetrics.QUEUE_DEPTH)),
                "the business metrics are used by the assets: " + referenced);

        Set<String> known = knownMetricNames();
        Set<String> unknown = new TreeSet<>(referenced);
        unknown.removeAll(known);
        assertTrue(unknown.isEmpty(), "metrics referenced in observability/datadog but not emitted by the code: " + unknown);
    }

    private static void assertWidgetShape(JsonNode widget) {
        JsonNode definition = widget.path("definition");
        assertTrue(definition.isObject(), "widget.definition is required");
        String type = requireText(definition, "type");
        if ("group".equals(type)) {
            JsonNode inner = definition.path("widgets");
            assertTrue(inner.isArray() && inner.size() > 0, "group widget has children");
            inner.forEach(DatadogAssetsTest::assertWidgetShape);
            return;
        }
        JsonNode requests = definition.path("requests");
        assertTrue(requests.isArray() && requests.size() > 0, type + " widget has requests");
        for (JsonNode request : requests) {
            assertTrue(request.has("q") || request.path("queries").isArray(),
                    type + " request has either q or queries");
        }
    }

    private static Set<String> metricNamesIn(Path file) throws IOException {
        Set<String> names = new TreeSet<>();
        Matcher matcher = METRIC_QUERY.matcher(Files.readString(file));
        while (matcher.find()) {
            String name = matcher.group(1);
            for (String suffix : DOGSTATSD_SUFFIXES) {
                if (name.endsWith(suffix)) {
                    name = name.substring(0, name.length() - suffix.length());
                    break;
                }
            }
            names.add(name);
        }
        assertFalse(names.isEmpty(), file + " references at least one metric");
        return names;
    }

    private Set<String> knownMetricNames() {
        Set<String> names = new TreeSet<>();
        for (Field field : ReportMetrics.class.getDeclaredFields()) {
            if (Modifier.isStatic(field.getModifiers()) && field.getType() == String.class
                    && field.getName().matches("[A-Z_]+") && !field.getName().startsWith("TAG_")) {
                try {
                    names.add((String) field.get(null));
                } catch (IllegalAccessException e) {
                    throw new IllegalStateException(e);
                }
            }
        }
        registry.getMeters().stream().map(Meter::getId).map(Meter.Id::getName).forEach(names::add);
        return names;
    }

    private static String requireText(JsonNode node, String field) {
        JsonNode value = node.path(field);
        assertTrue(value.isTextual() && !value.asText().isBlank(), "'" + field + "' must be a non-empty string in " + node);
        return value.asText();
    }
}
