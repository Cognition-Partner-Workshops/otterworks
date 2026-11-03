package com.otterworks.ottershops.ops;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

/** Moves pickup orders to READY_FOR_PICKUP once the store's pick window has passed. */
@Component
public class PickupReadyJob {
    public static final String JOB = "pickup-ready";
    private static final Logger log = LoggerFactory.getLogger(PickupReadyJob.class);

    private final JdbcTemplate jdbc;
    private final JobRunRepository runs;

    public PickupReadyJob(JdbcTemplate jdbc, JobRunRepository runs) {
        this.jdbc = jdbc;
        this.runs = runs;
    }

    @Scheduled(initialDelayString = "PT1M", fixedDelayString = "${ottershops.jobs.pickup-ready-ms:300000}")
    public void scheduled() {
        run();
    }

    public synchronized void run() {
        long id = runs.start(JOB, null);
        int n = jdbc.update("""
                UPDATE orders o SET status = 'READY_FOR_PICKUP', updated_at = now()
                FROM stores s
                WHERE s.id = o.store_id AND s.pickup_enabled
                  AND o.fulfillment = 'PICKUP' AND o.status = 'PLACED'
                  AND o.created_at + make_interval(hours => s.pickup_ready_hours) <= now()""");
        runs.finish(id, "SUCCEEDED", n, n, null);
        if (n > 0) log.info("pickup-ready: {} orders ready for pickup", n);
    }
}
