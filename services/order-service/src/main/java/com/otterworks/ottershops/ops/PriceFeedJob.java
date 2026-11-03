package com.otterworks.ottershops.ops;

import com.otterworks.ottershops.catalog.CatalogService;
import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Comparator;
import java.util.List;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.Resource;
import org.springframework.core.io.support.PathMatchingResourcePatternResolver;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import org.springframework.transaction.support.TransactionTemplate;

/**
 * Nightly merchandising price feed. Each file is applied all-or-nothing and only once; a file that fails is
 * retried on the next run.
 */
@Component
public class PriceFeedJob {
    public static final String JOB = "price-feed";
    static final String HEADER = "product_id,list_price_cents,markdown_price_cents";
    private static final Logger log = LoggerFactory.getLogger(PriceFeedJob.class);

    private final JdbcTemplate jdbc;
    private final TransactionTemplate tx;
    private final JobRunRepository runs;
    private final CatalogService catalog;
    private final String location;

    public PriceFeedJob(JdbcTemplate jdbc, TransactionTemplate tx, JobRunRepository runs, CatalogService catalog,
                        @Value("${ottershops.feeds.prices:classpath*:feeds/prices/*.csv}") String location) {
        this.jdbc = jdbc;
        this.tx = tx;
        this.runs = runs;
        this.catalog = catalog;
        this.location = location;
    }

    @Scheduled(cron = "${ottershops.feeds.price-cron:0 15 2 * * *}", zone = "America/Los_Angeles")
    public void nightly() {
        run();
    }

    public synchronized List<JobRunRepository.JobRun> run() {
        Resource[] files;
        try {
            files = new PathMatchingResourcePatternResolver().getResources(location);
        } catch (IOException e) {
            log.error("price feed: cannot list {}", location, e);
            return List.of();
        }
        Arrays.sort(files, Comparator.comparing(Resource::getFilename));
        boolean applied = false;
        for (Resource file : files) {
            String name = file.getFilename();
            if (runs.succeeded(JOB, name)) continue;
            long id = runs.start(JOB, name);
            try {
                List<String[]> rows = read(file);
                int n = tx.execute(s -> apply(rows));
                runs.finish(id, "SUCCEEDED", rows.size(), n, null);
                log.info("price feed {} applied: {} rows, {} products updated", name, rows.size(), n);
                applied = true;
            } catch (FeedException | IOException | RuntimeException e) {
                runs.finish(id, "FAILED", 0, 0, e.getMessage());
                log.error("price feed {} failed: {}", name, e.getMessage());
            }
        }
        if (applied) catalog.refresh();
        return runs.recent(JOB, files.length);
    }

    private static List<String[]> read(Resource file) throws IOException, FeedException {
        try (BufferedReader in = new BufferedReader(new InputStreamReader(file.getInputStream(), StandardCharsets.UTF_8))) {
            String header = in.readLine();
            if (header == null || !header.trim().equals(HEADER)) {
                throw new FeedException("unexpected header [" + header + "], expected [" + HEADER + "]");
            }
            List<String[]> rows = new ArrayList<>();
            String line;
            int lineNo = 1;
            while ((line = in.readLine()) != null) {
                lineNo++;
                if (line.isBlank()) continue;
                String[] f = line.split(",", -1);
                if (f.length != 3 || f[0].isBlank() || !f[1].trim().matches("\\d+") || !f[2].trim().matches("\\d*")) {
                    throw new FeedException("line " + lineNo + " is malformed: " + line);
                }
                rows.add(f);
            }
            return rows;
        }
    }

    private int apply(List<String[]> rows) {
        int updated = 0;
        for (String[] f : rows) {
            Integer markdown = f[2].isBlank() ? null : Integer.valueOf(f[2].trim());
            int n = jdbc.update("UPDATE products SET list_price_cents = ?, markdown_price_cents = ? WHERE id = ?",
                    Integer.valueOf(f[1].trim()), markdown, f[0].trim());
            if (n == 0) throw new IllegalStateException("unknown product " + f[0].trim());
            updated += n;
        }
        return updated;
    }

    static class FeedException extends Exception {
        FeedException(String message) {
            super(message);
        }
    }
}
