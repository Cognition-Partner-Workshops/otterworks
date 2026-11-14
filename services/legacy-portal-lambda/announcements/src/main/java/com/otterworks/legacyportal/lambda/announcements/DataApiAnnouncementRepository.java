package com.otterworks.legacyportal.lambda.announcements;

import java.time.Duration;
import java.time.Instant;
import java.time.LocalDateTime;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.time.format.DateTimeFormatterBuilder;
import java.time.temporal.ChronoField;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import java.util.concurrent.ThreadLocalRandom;

import software.amazon.awssdk.core.client.config.ClientOverrideConfiguration;
import software.amazon.awssdk.services.rdsdata.RdsDataClient;
import software.amazon.awssdk.services.rdsdata.model.DatabaseResumingException;
import software.amazon.awssdk.services.rdsdata.model.ExecuteStatementRequest;
import software.amazon.awssdk.services.rdsdata.model.ExecuteStatementResponse;
import software.amazon.awssdk.services.rdsdata.model.Field;
import software.amazon.awssdk.services.rdsdata.model.SqlParameter;

/**
 * Announcement persistence through the RDS Data API. The table lives in the context's own
 * schema ({@code DB_SCHEMA}) on the shared Aurora cluster; {@code created_at} is a
 * {@code timestamp without time zone} kept in UTC, like the monolith's JPA mapping.
 */
public class DataApiAnnouncementRepository implements AnnouncementRepository {

    // Sends always carry the full microsecond precision Postgres stores; the Data API
    // may hand a timestamp back with a shortened or absent fraction.
    static final DateTimeFormatter TS_WRITE = new DateTimeFormatterBuilder()
            .appendPattern("yyyy-MM-dd HH:mm:ss")
            .appendFraction(ChronoField.MICRO_OF_SECOND, 6, 6, true)
            .toFormatter();

    static final DateTimeFormatter TS_FORMAT = new DateTimeFormatterBuilder()
            .appendPattern("yyyy-MM-dd HH:mm:ss")
            .optionalStart()
            .appendFraction(ChronoField.MICRO_OF_SECOND, 1, 6, true)
            .optionalEnd()
            .toFormatter();

    // Retry window for a paused cluster plus one call must stay under the 29 s Lambda timeout.
    static final long RETRY_WINDOW_NANOS = 20_000_000_000L;
    static final Duration API_CALL_TIMEOUT = Duration.ofSeconds(8);
    static final long MAX_DELAY_MILLIS = 3_000;

    interface RetryClock {
        long nanoTime();

        void sleep(long nanos) throws InterruptedException;
    }

    static final RetryClock SYSTEM_CLOCK = new RetryClock() {
        @Override
        public long nanoTime() {
            return System.nanoTime();
        }

        @Override
        public void sleep(long nanos) throws InterruptedException {
            Thread.sleep(nanos / 1_000_000L, (int) (nanos % 1_000_000L));
        }
    };

    private final RdsDataClient client;
    private final String clusterArn;
    private final String secretArn;
    private final String database;
    private final String table;
    private final RetryClock clock;

    public DataApiAnnouncementRepository(RdsDataClient client, String clusterArn, String secretArn,
            String database, String schema) {
        this(client, clusterArn, secretArn, database, schema, SYSTEM_CLOCK);
    }

    DataApiAnnouncementRepository(RdsDataClient client, String clusterArn, String secretArn,
            String database, String schema, RetryClock clock) {
        this.clock = clock;
        this.client = client;
        this.clusterArn = clusterArn;
        this.secretArn = secretArn;
        this.database = database;
        this.table = schema + ".announcement";
    }

    /**
     * Total deadline per ExecuteStatement including SDK retries. No per-attempt timeout: the
     * SDK retries attempt timeouts, which could run a committed INSERT a second time.
     */
    public static ClientOverrideConfiguration clientOverrides() {
        return ClientOverrideConfiguration.builder().apiCallTimeout(API_CALL_TIMEOUT).build();
    }

    @Override
    public Announcement save(Announcement announcement) {
        if (announcement.getId() == null) {
            ExecuteStatementResponse response = execute(
                    "INSERT INTO " + table
                            + " (title, body, published, created_at) VALUES (:title, :body, :published, CAST(:created_at AS timestamp))"
                            + " RETURNING id, title, body, published, created_at",
                    params(announcement));
            return row(response.records().get(0));
        }
        execute("UPDATE " + table
                        + " SET title = :title, body = :body, published = :published, created_at = CAST(:created_at AS timestamp)"
                        + " WHERE id = :id",
                params(announcement));
        return announcement;
    }

    @Override
    public List<Announcement> findByPublishedTrueOrderByCreatedAtDesc() {
        ExecuteStatementResponse response = execute(
                "SELECT id, title, body, published, created_at FROM " + table
                        + " WHERE published = true ORDER BY created_at DESC");
        return rows(response);
    }

    @Override
    public List<Announcement> findAll() {
        ExecuteStatementResponse response = execute(
                "SELECT id, title, body, published, created_at FROM " + table);
        return rows(response);
    }

    @Override
    public Optional<Announcement> findById(Long id) {
        ExecuteStatementResponse response = execute(
                "SELECT id, title, body, published, created_at FROM " + table + " WHERE id = :id",
                List.of(SqlParameter.builder().name("id").value(Field.builder()
                        .longValue(id).build()).build()));
        if (response.records().isEmpty()) {
            return Optional.empty();
        }
        return Optional.of(row(response.records().get(0)));
    }

    private List<SqlParameter> params(Announcement a) {
        List<SqlParameter> params = new ArrayList<>();
        if (a.getId() != null) {
            params.add(param("id", Field.builder().longValue(a.getId()).build()));
        }
        params.add(param("title", Field.builder().stringValue(a.getTitle()).build()));
        params.add(param("body", Field.builder().stringValue(a.getBody()).build()));
        params.add(param("published", Field.builder().booleanValue(a.isPublished()).build()));
        params.add(param("created_at", Field.builder()
                .stringValue(TS_WRITE.format(LocalDateTime.ofInstant(a.getCreatedAt(), ZoneOffset.UTC)))
                .build()));
        return params;
    }

    private static SqlParameter param(String name, Field value) {
        return SqlParameter.builder().name(name).value(value).build();
    }

    private List<Announcement> rows(ExecuteStatementResponse response) {
        List<Announcement> out = new ArrayList<>(response.records().size());
        for (List<Field> record : response.records()) {
            out.add(row(record));
        }
        return out;
    }

    private static Announcement row(List<Field> record) {
        Announcement a = new Announcement();
        a.setId(record.get(0).longValue());
        a.setTitle(record.get(1).stringValue());
        a.setBody(record.get(2).stringValue());
        a.setPublished(Boolean.TRUE.equals(record.get(3).booleanValue()));
        a.setCreatedAt(LocalDateTime.parse(record.get(4).stringValue(), TS_FORMAT)
                .toInstant(ZoneOffset.UTC));
        return a;
    }

    private ExecuteStatementResponse execute(String sql) {
        return execute(sql, List.of());
    }

    private ExecuteStatementResponse execute(String sql, List<SqlParameter> parameters) {
        ExecuteStatementRequest request = ExecuteStatementRequest.builder()
                .resourceArn(clusterArn)
                .secretArn(secretArn)
                .database(database)
                .sql(sql)
                .parameters(parameters)
                .build();
        // Aurora Serverless v2 can be paused at 0 ACU; the Data API answers
        // DatabaseResumingException (statement not run) until the cluster is warm again.
        long started = clock.nanoTime();
        int attempt = 0;
        while (true) {
            try {
                return client.executeStatement(request);
            } catch (DatabaseResumingException e) {
                long remaining = RETRY_WINDOW_NANOS - (clock.nanoTime() - started);
                if (remaining <= 0) {
                    throw e;
                }
                try {
                    clock.sleep(Math.min(remaining, backoffMillis(++attempt) * 1_000_000L));
                } catch (InterruptedException ie) {
                    Thread.currentThread().interrupt();
                    throw e;
                }
            }
        }
    }

    /** Linear growth capped at 3 s, with equal jitter so cold-start callers spread out. */
    static long backoffMillis(int attempt) {
        long ceiling = Math.min(500L * attempt, MAX_DELAY_MILLIS);
        return ceiling / 2 + ThreadLocalRandom.current().nextLong(ceiling / 2 + 1);
    }
}
