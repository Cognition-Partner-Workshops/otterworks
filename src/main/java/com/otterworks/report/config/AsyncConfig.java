package com.otterworks.report.config;

import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.binder.jvm.ExecutorServiceMetrics;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Primary;
import org.springframework.scheduling.concurrent.ThreadPoolTaskExecutor;

import java.util.Collections;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.ThreadPoolExecutor;

/**
 * Explicit, bounded executors for report generation and upstream fan-out.
 *
 * <p>{@code reportGenerationExecutor} is the {@code @Async} executor used by
 * {@code ReportGenerationWorker}; when its queue is full the submitting thread runs the
 * task itself ({@link ThreadPoolExecutor.CallerRunsPolicy}) so back-pressure reaches the caller
 * instead of tasks being dropped. Metrics: {@code executor.*} tagged {@code name=report-gen}.
 */
@Configuration
@EnableConfigurationProperties(ReportProperties.class)
public class AsyncConfig {

    public static final String REPORT_GENERATION_EXECUTOR = "reportGenerationExecutor";
    public static final String FETCH_EXECUTOR = "reportFetchExecutor";

    @Bean(name = REPORT_GENERATION_EXECUTOR)
    @Primary
    public ThreadPoolTaskExecutor reportGenerationExecutor(ReportProperties props, MeterRegistry registry) {
        ReportProperties.Executor cfg = props.executor();
        ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
        executor.setCorePoolSize(cfg.coreSize());
        executor.setMaxPoolSize(cfg.maxSize());
        executor.setQueueCapacity(cfg.queueCapacity());
        executor.setThreadNamePrefix("report-gen-");
        executor.setRejectedExecutionHandler(new ThreadPoolExecutor.CallerRunsPolicy());
        executor.setWaitForTasksToCompleteOnShutdown(true);
        executor.setAwaitTerminationSeconds(30);
        executor.initialize();
        new ExecutorServiceMetrics(executor.getThreadPoolExecutor(), "report-gen", Collections.emptyList())
                .bindTo(registry);
        return executor;
    }

    @Bean(name = FETCH_EXECUTOR, destroyMethod = "shutdown")
    public ExecutorService reportFetchExecutor(ReportProperties props, MeterRegistry registry) {
        ExecutorService executor = Executors.newFixedThreadPool(props.fetch().parallelism(), runnable -> {
            Thread thread = new Thread(runnable);
            thread.setName("report-fetch-" + thread.threadId());
            thread.setDaemon(true);
            return thread;
        });
        return ExecutorServiceMetrics.monitor(registry, executor, "report-fetch");
    }
}
