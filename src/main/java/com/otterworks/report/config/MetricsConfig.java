package com.otterworks.report.config;

import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.Tag;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.actuate.autoconfigure.metrics.MeterRegistryCustomizer;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.scheduling.concurrent.ThreadPoolTaskExecutor;

import java.util.List;

@Configuration
public class MetricsConfig {

    @Value("${DD_SERVICE:report-service}")
    private String ddService;

    @Value("${DD_ENV:local}")
    private String ddEnv;

    @Value("${DD_VERSION:0.1.0}")
    private String ddVersion;

    @Bean
    public MeterRegistryCustomizer<MeterRegistry> commonTags() {
        return registry -> registry.config().commonTags(
                List.of(
                        Tag.of("service", ddService),
                        Tag.of("env", ddEnv),
                        Tag.of("version", ddVersion)
                )
        );
    }

    @Bean
    public Object reportQueueDepthGauge(MeterRegistry meterRegistry, ThreadPoolTaskExecutor reportGenerationExecutor) {
        meterRegistry.gauge("reports.queue.depth", reportGenerationExecutor,
                executor -> executor.getThreadPoolExecutor().getQueue().size() +
                        executor.getThreadPoolExecutor().getActiveCount());
        return new Object(); // bean placeholder
    }
}
