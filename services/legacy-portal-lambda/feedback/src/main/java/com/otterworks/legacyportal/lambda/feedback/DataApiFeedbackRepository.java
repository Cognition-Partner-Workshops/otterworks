package com.otterworks.legacyportal.lambda.feedback;

import java.time.Duration;
import java.time.Instant;
import java.time.LocalDateTime;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.concurrent.ThreadLocalRandom;
import java.util.function.Supplier;
import java.util.regex.Pattern;
import software.amazon.awssdk.core.client.config.ClientOverrideConfiguration;
import software.amazon.awssdk.regions.Region;
import software.amazon.awssdk.services.rdsdata.RdsDataClient;
import software.amazon.awssdk.services.rdsdata.model.ExecuteStatementRequest;
import software.amazon.awssdk.services.rdsdata.model.ExecuteStatementResponse;
import software.amazon.awssdk.services.rdsdata.model.Field;
import software.amazon.awssdk.services.rdsdata.model.SqlParameter;
import software.amazon.awssdk.services.rdsdata.model.TypeHint;
import software.amazon.awssdk.http.urlconnection.UrlConnectionHttpClient;

public final class DataApiFeedbackRepository implements FeedbackRepository {
    private static final Pattern SCHEMA_NAME = Pattern.compile("[A-Za-z_][A-Za-z0-9_]*");
    // Retry window for a paused cluster plus one call must stay under the 29 s Lambda timeout.
    static final long RETRY_WINDOW_NANOS = 20_000_000_000L;
    static final Duration API_CALL_TIMEOUT = Duration.ofSeconds(8);
    static final long BASE_DELAY_MILLIS = 250;
    static final long MAX_DELAY_MILLIS = 3_000;
    private static final DateTimeFormatter CREATED_AT_FORMAT =
            DateTimeFormatter.ofPattern("uuuu-MM-dd HH:mm:ss.SSSSSS", Locale.ROOT);

    interface RetryClock {
        long nanoTime();

        void sleep(long nanos) throws InterruptedException;
    }

    static final RetryClock SYSTEM_CLOCK =
            new RetryClock() {
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

    public DataApiFeedbackRepository() {
        this(
                createClient(),
                requiredEnvironment("CLUSTER_ARN"),
                requiredEnvironment("SECRET_ARN"),
                requiredEnvironment("DB_NAME"),
                requiredSchema());
    }

    DataApiFeedbackRepository(
            RdsDataClient client, String clusterArn, String secretArn, String database, String schema) {
        this(client, clusterArn, secretArn, database, schema, SYSTEM_CLOCK);
    }

    DataApiFeedbackRepository(
            RdsDataClient client, String clusterArn, String secretArn, String database, String schema,
            RetryClock clock) {
        if (!SCHEMA_NAME.matcher(schema).matches()) {
            throw new IllegalArgumentException("DB_SCHEMA must be a SQL identifier");
        }
        this.client = client;
        this.clusterArn = clusterArn;
        this.secretArn = secretArn;
        this.database = database;
        this.table = schema + ".feedback";
        this.clock = clock;
    }

    /**
     * Total deadline per ExecuteStatement including SDK retries. No per-attempt timeout: the
     * SDK retries attempt timeouts, which could run a committed INSERT a second time.
     */
    static ClientOverrideConfiguration clientOverrides() {
        return ClientOverrideConfiguration.builder().apiCallTimeout(API_CALL_TIMEOUT).build();
    }

    @Override
    public Feedback save(Feedback feedback) {
        String createdAt = CREATED_AT_FORMAT.withZone(ZoneOffset.UTC).format(feedback.createdAt());
        String sql = "INSERT INTO " + table
                + " (created_at, message, rating, user_id) "
                + "VALUES (:createdAt, :message, :rating, :userId) RETURNING id";
        // A lost connection leaves the INSERT's outcome unknown; only a resuming cluster
        // (statement not run) is safe to retry without duplicating the row.
        ExecuteStatementResponse response = execute(sql, false,
                List.of(
                        stringParameter("createdAt", createdAt, TypeHint.TIMESTAMP),
                        stringParameter("message", feedback.message(), null),
                        longParameter("rating", feedback.rating()),
                        stringParameter("userId", feedback.userId(), null)));
        long id = response.records().get(0).get(0).longValue();
        return new Feedback(id, feedback.userId(), feedback.rating(), feedback.message(), feedback.createdAt());
    }

    @Override
    public List<Feedback> findByUserId(String userId) {
        String sql = "SELECT id, created_at, message, rating, user_id FROM " + table
                + " WHERE user_id = :userId ORDER BY created_at DESC, id DESC";
        ExecuteStatementResponse response = execute(
                sql, true, List.of(stringParameter("userId", userId, null)));
        List<Feedback> feedback = new ArrayList<>();
        for (List<Field> row : response.records()) {
            feedback.add(new Feedback(
                    row.get(0).longValue(),
                    row.get(4).stringValue(),
                    row.get(3).longValue().intValue(),
                    row.get(2).stringValue(),
                    parseTimestamp(row.get(1).stringValue())));
        }
        return feedback;
    }

    @Override
    public FeedbackAggregates aggregate() {
        String sql = "SELECT count(*), coalesce(sum(rating), 0) FROM " + table;
        List<Field> values = execute(sql, true, List.of()).records().get(0);
        return new FeedbackAggregates(values.get(0).longValue(), values.get(1).longValue());
    }

    private ExecuteStatementResponse execute(
            String sql, boolean idempotent, List<SqlParameter> parameters) {
        return retry(idempotent, () -> client.executeStatement(ExecuteStatementRequest.builder()
                .resourceArn(clusterArn)
                .secretArn(secretArn)
                .database(database)
                .sql(sql)
                .parameters(parameters)
                .build()));
    }

    private <T> T retry(boolean idempotent, Supplier<T> action) {
        long started = clock.nanoTime();
        long delayMillis = BASE_DELAY_MILLIS;
        while (true) {
            try {
                return action.get();
            } catch (RuntimeException exception) {
                long remaining = RETRY_WINDOW_NANOS - (clock.nanoTime() - started);
                if (!isRetryable(exception, idempotent) || remaining <= 0) {
                    throw exception;
                }
                long jittered = delayMillis / 2 + ThreadLocalRandom.current().nextLong(delayMillis / 2 + 1);
                try {
                    clock.sleep(Math.min(remaining, jittered * 1_000_000L));
                } catch (InterruptedException interrupted) {
                    Thread.currentThread().interrupt();
                    throw new IllegalStateException("Interrupted while waiting for the database", interrupted);
                }
                delayMillis = Math.min(delayMillis * 2, MAX_DELAY_MILLIS);
            }
        }
    }

    private boolean isRetryable(Throwable exception, boolean idempotent) {
        for (Throwable current = exception; current != null; current = current.getCause()) {
            if (current.getClass().getSimpleName().equals("DatabaseResumingException")) {
                return true;
            }
            String message = current.getMessage();
            if (idempotent && message != null && message.toLowerCase(Locale.ROOT).contains("communications link failure")) {
                return true;
            }
        }
        return false;
    }

    private static SqlParameter stringParameter(String name, String value, TypeHint typeHint) {
        SqlParameter.Builder builder = SqlParameter.builder()
                .name(name)
                .value(Field.builder().stringValue(value).build());
        if (typeHint != null) {
            builder.typeHint(typeHint);
        }
        return builder.build();
    }

    private static SqlParameter longParameter(String name, long value) {
        return SqlParameter.builder()
                .name(name)
                .value(Field.builder().longValue(value).build())
                .build();
    }

    private static Instant parseTimestamp(String value) {
        int separator = value.indexOf(' ');
        String normalized = separator >= 0
                ? value.substring(0, separator) + "T" + value.substring(separator + 1)
                : value;
        return LocalDateTime.parse(normalized, DateTimeFormatter.ISO_LOCAL_DATE_TIME)
                .toInstant(ZoneOffset.UTC);
    }

    private static RdsDataClient createClient() {
        String region = System.getenv().getOrDefault("AWS_REGION", "us-east-1");
        return RdsDataClient.builder()
                .region(Region.of(region))
                .httpClientBuilder(UrlConnectionHttpClient.builder())
                .overrideConfiguration(clientOverrides())
                .build();
    }

    private static String requiredEnvironment(String name) {
        String value = System.getenv(name);
        if (value == null || value.isBlank()) {
            throw new IllegalStateException("Missing required environment variable " + name);
        }
        return value;
    }

    private static String requiredSchema() {
        String schema = System.getenv().getOrDefault("DB_SCHEMA", "feedback");
        if (schema.isBlank()) {
            throw new IllegalStateException("Missing required environment variable DB_SCHEMA");
        }
        return schema;
    }
}
