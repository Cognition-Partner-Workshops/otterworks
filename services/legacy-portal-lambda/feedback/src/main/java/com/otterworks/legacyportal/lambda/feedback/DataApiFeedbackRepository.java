package com.otterworks.legacyportal.lambda.feedback;

import java.time.Instant;
import java.time.LocalDateTime;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.function.Supplier;
import java.util.regex.Pattern;
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
    private static final long RETRY_WINDOW_NANOS = 20_000_000_000L;
    private static final DateTimeFormatter CREATED_AT_FORMAT =
            DateTimeFormatter.ofPattern("uuuu-MM-dd HH:mm:ss.SSSSSS", Locale.ROOT);

    private final RdsDataClient client;
    private final String clusterArn;
    private final String secretArn;
    private final String database;
    private final String table;

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
        if (!SCHEMA_NAME.matcher(schema).matches()) {
            throw new IllegalArgumentException("DB_SCHEMA must be a SQL identifier");
        }
        this.client = client;
        this.clusterArn = clusterArn;
        this.secretArn = secretArn;
        this.database = database;
        this.table = schema + ".feedback";
    }

    @Override
    public Feedback save(Feedback feedback) {
        String createdAt = CREATED_AT_FORMAT.withZone(ZoneOffset.UTC).format(feedback.createdAt());
        String sql = "INSERT INTO " + table
                + " (created_at, message, rating, user_id) "
                + "VALUES (:createdAt, :message, :rating, :userId) RETURNING id";
        ExecuteStatementResponse response = execute(sql,
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
                sql, List.of(stringParameter("userId", userId, null)));
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
        List<Field> values = execute(sql, List.of()).records().get(0);
        return new FeedbackAggregates(values.get(0).longValue(), values.get(1).longValue());
    }

    private ExecuteStatementResponse execute(String sql, List<SqlParameter> parameters) {
        return retry(() -> client.executeStatement(ExecuteStatementRequest.builder()
                .resourceArn(clusterArn)
                .secretArn(secretArn)
                .database(database)
                .sql(sql)
                .parameters(parameters)
                .build()));
    }

    private <T> T retry(Supplier<T> action) {
        long started = System.nanoTime();
        long delayMillis = 250;
        while (true) {
            try {
                return action.get();
            } catch (RuntimeException exception) {
                long remaining = RETRY_WINDOW_NANOS - (System.nanoTime() - started);
                if (!isRetryable(exception) || remaining <= 0) {
                    throw exception;
                }
                long pauseNanos = Math.min(remaining, delayMillis * 1_000_000L);
                try {
                    long millis = pauseNanos / 1_000_000L;
                    int nanos = (int) (pauseNanos % 1_000_000L);
                    Thread.sleep(millis, nanos);
                } catch (InterruptedException interrupted) {
                    Thread.currentThread().interrupt();
                    throw new IllegalStateException("Interrupted while waiting for the database", interrupted);
                }
                delayMillis = Math.min(delayMillis * 2, 3_000);
            }
        }
    }

    private boolean isRetryable(Throwable exception) {
        for (Throwable current = exception; current != null; current = current.getCause()) {
            if (current.getClass().getSimpleName().equals("DatabaseResumingException")) {
                return true;
            }
            String message = current.getMessage();
            if (message != null && message.toLowerCase(Locale.ROOT).contains("communications link failure")) {
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
