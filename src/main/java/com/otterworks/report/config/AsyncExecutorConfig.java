package com.otterworks.report.config;

import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.binder.jvm.ExecutorServiceMetrics;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.scheduling.concurrent.ThreadPoolTaskExecutor;

import java.util.concurrent.Executor;

@Configuration
public class AsyncExecutorConfig {

    @Value("${otterworks.report.executor.core-size:4}")
    private int coreSize;

    @Value("${otterworks.report.executor.max-size:8}")
    private int maxSize;

    @Value("${otterworks.report.executor.queue-capacity:100}")
    private int queueCapacity;

    @Bean(name = "reportGenerationExecutor")
    public ThreadPoolTaskExecutor reportGenerationExecutor(MeterRegistry meterRegistry) {
        ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
        executor.setCorePoolSize(coreSize);
        executor.setMaxPoolSize(maxSize);
        executor.setQueueCapacity(queueCapacity);
        executor.setThreadNamePrefix("report-gen-");
        executor.setRejectedExecutionHandler(new java.util.concurrent.ThreadPoolExecutor.CallerRunsPolicy());
        executor.initialize();

        // Register executor metrics
        ExecutorServiceMetrics.monitor(meterRegistry, executor.getThreadPoolExecutor(), "reportGenerationExecutor");

        return executor;
    }
}
