package com.otterworks.report.config;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.boot.context.properties.bind.DefaultValue;

import java.time.Duration;

/**
 * Tunables for the report pipeline (bound from {@code otterworks.report.*}).
 */
@ConfigurationProperties(prefix = "otterworks.report")
public record ReportProperties(
        @DefaultValue Cache cache,
        @DefaultValue Executor executor,
        @DefaultValue Fetch fetch,
        @DefaultValue Schedule schedule) {

    public record Cache(@DefaultValue("100") long maxSize, @DefaultValue("5m") Duration ttl) {
    }

    public record Executor(
            @DefaultValue("4") int coreSize,
            @DefaultValue("8") int maxSize,
            @DefaultValue("100") int queueCapacity) {
    }

    public record Fetch(@DefaultValue("4") int parallelism) {
    }

    public record Schedule(@DefaultValue("60s") Duration pollInterval) {
    }
}
