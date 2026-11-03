package com.otterworks.ottershops.warehouse;

import com.otterworks.ottershops.ops.JobRunRepository;
import java.time.Clock;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

/** Releases placed ship-to-home orders to the 3PL as one CSV file per run. */
@Component
public class WarehouseExportJob {
    public static final String JOB = "warehouse-export";
    public static final String HEADER = "order_number,ship_name,ship_line1,ship_line2,ship_city,ship_state,ship_zip,sku,quantity";
    static final int MAX_ORDERS = 200;
    private static final Logger log = LoggerFactory.getLogger(WarehouseExportJob.class);
    private static final DateTimeFormatter FILE_TS = DateTimeFormatter.ofPattern("yyyyMMdd_HHmm");

    private final JdbcTemplate jdbc;
    private final ThreePlGateway gateway;
    private final JobRunRepository runs;
    private final Clock clock;

    public WarehouseExportJob(JdbcTemplate jdbc, ThreePlGateway gateway, JobRunRepository runs, Clock clock) {
        this.jdbc = jdbc;
        this.gateway = gateway;
        this.runs = runs;
        this.clock = clock;
    }

    @Scheduled(initialDelayString = "PT2M", fixedDelayString = "${ottershops.jobs.warehouse-export-ms:900000}")
    public void scheduled() {
        run();
    }

    @Transactional
    public synchronized void run() {
        String fileName = "OTTER_ORD_" + FILE_TS.format(clock.instant().atZone(ZoneId.of("America/Los_Angeles"))) + ".csv";
        long runId = runs.start(JOB, fileName);
        List<Map<String, Object>> rows = jdbc.queryForList("""
                SELECT o.id, o.order_number, o.ship_name, o.ship_line1, o.ship_line2, o.ship_city, o.ship_state, o.ship_zip,
                       l.sku, l.quantity
                FROM orders o JOIN order_lines l ON l.order_id = o.id
                WHERE o.id IN (SELECT id FROM orders WHERE fulfillment = 'SHIP' AND status = 'PLACED'
                               ORDER BY created_at LIMIT ?)
                ORDER BY o.created_at, l.line_no""", MAX_ORDERS);
        if (rows.isEmpty()) {
            runs.finish(runId, "SUCCEEDED", 0, 0, "nothing to release");
            return;
        }
        Set<UUID> orderIds = new LinkedHashSet<>();
        StringBuilder csv = new StringBuilder(HEADER).append('\n');
        for (Map<String, Object> r : rows) {
            orderIds.add((UUID) r.get("id"));
            List<String> fields = new ArrayList<>();
            for (String col : HEADER.split(",")) {
                Object v = "order_number".equals(col) ? r.get("order_number") : r.get(col);
                fields.add(v == null ? "" : v.toString());
            }
            csv.append(String.join(",", fields)).append('\n');
        }
        ThreePlGateway.Ack ack = gateway.submit(fileName, csv.toString());
        jdbc.update("""
                INSERT INTO warehouse_batches (file_name, status, order_count, line_count, error, payload)
                VALUES (?, ?, ?, ?, ?, ?)""", fileName, ack.accepted() ? "ACCEPTED" : "REJECTED", orderIds.size(),
                rows.size(), ack.error(), csv.toString());
        if (!ack.accepted()) {
            runs.finish(runId, "FAILED", orderIds.size(), 0, ack.error());
            log.error("warehouse export {} rejected by 3PL: {} ({} orders held)", fileName, ack.error(), orderIds.size());
            return;
        }
        int released = jdbc.update("UPDATE orders SET status = 'RELEASED_TO_WAREHOUSE', updated_at = now() WHERE id = ANY(?)",
                (Object) orderIds.toArray(new UUID[0]));
        runs.finish(runId, "SUCCEEDED", orderIds.size(), released, null);
        log.info("warehouse export {} accepted: {} orders, {} lines", fileName, released, rows.size());
    }
}
