package com.otterworks.legacyportal.lambda.feedback;

import java.time.Instant;
import java.time.LocalDateTime;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.time.format.DateTimeFormatterBuilder;
import java.time.temporal.ChronoField;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Objects;
import java.util.function.Supplier;
import java.util.regex.Pattern;
import software.amazon.awssdk.awscore.exception.AwsServiceException;
import software.amazon.awssdk.regions.Region;
import software.amazon.awssdk.services.rdsdata.RdsDataClient;
import software.amazon.awssdk.services.rdsdata.model.ExecuteStatementRequest;
import software.amazon.awssdk.services.rdsdata.model.ExecuteStatementResponse;
import software.amazon.awssdk.services.rdsdata.model.Field;
import software.amazon.awssdk.services.rdsdata.model.SqlParameter;
import software.amazon.awssdk.services.rdsdata.model.TypeHint;
import software.amazon.awssdk.http.urlconnection.UrlConnectionHttpClient;

public class DataApiFeedbackStore implements FeedbackStore {

    private static final Pattern VALID_SCHEMA = Pattern.compile("^[a-z_]+$");
    private static final DateTimeFormatter TIMESTAMP_FORMAT =
            DateTimeFormatter.ofPattern("uuuu-MM-dd HH:mm:ss.SSSSSS", Locale.ROOT);
    private static final DateTimeFormatter DATABASE_TIMESTAMP_FORMAT =
            new DateTimeFormatterBuilder()
                    .appendPattern("uuuu-MM-dd HH:mm:ss")
                    .optionalStart()
                    .appendFraction(ChronoField.NANO_OF_SECOND, 1, 9, true)
                    .optionalEnd()
                    .toFormatter(Locale.ROOT);
    private static final long RETRY_WINDOW_NANOS = 20_000_000_000L;
    private static final long INITIAL_BACKOFF_MILLIS = 200;
    private static final long MAX_BACKOFF_MILLIS = 2_000;

    private final String resourceArn;
    private final String secretArn;
    private final String database;
    private final String table;

    public DataApiFeedbackStore(Map<String, String> environment) {
        resourceArn = required(environment, "CLUSTER_ARN");
        secretArn = required(environment, "SECRET_ARN");
        database = required(environment, "DB_NAME");
        String schema = required(environment, "DB_SCHEMA");
        if (!VALID_SCHEMA.matcher(schema).matches()) {
            throw new IllegalArgumentException("DB_SCHEMA must contain only lowercase letters and underscores");
        }
        table = schema + ".feedback";
    }

    @Override
    public Feedback save(Feedback feedback) {
        ExecuteStatementResponse response = execute(() -> client().executeStatement(
                baseRequest("INSERT INTO " + table
                        + " (created_at, message, rating, user_id) "
                        + "VALUES (:created_at, :message, :rating, :user_id) RETURNING id")
                        .parameters(
                                timestampParameter("created_at", feedback.createdAt()),
                                stringParameter("message", feedback.message()),
                                longParameter("rating", feedback.rating()),
                                stringParameter("user_id", feedback.userId()))
                        .build()));
        long id = longValue(response.records().getFirst().getFirst());
        return new Feedback(id, feedback.userId(), feedback.rating(), feedback.message(), feedback.createdAt());
    }

    @Override
    public List<Feedback> findByUserIdOrderByCreatedAtDesc(String userId) {
        ExecuteStatementResponse response = execute(() -> client().executeStatement(
                baseRequest("SELECT id, user_id, rating, message, created_at FROM " + table
                        + " WHERE user_id = :user_id ORDER BY created_at DESC")
                        .parameters(stringParameter("user_id", userId))
                        .build()));
        List<Feedback> feedback = new ArrayList<>(response.records().size());
        for (List<Field> record : response.records()) {
            feedback.add(new Feedback(
                    longValue(record.get(0)),
                    stringValue(record.get(1)),
                    Math.toIntExact(longValue(record.get(2))),
                    stringValue(record.get(3)),
                    parseTimestamp(stringValue(record.get(4)))));
        }
        return feedback;
    }

    @Override
    public double averageRating() {
        ExecuteStatementResponse response = execute(() -> client().executeStatement(
                baseRequest("SELECT count(*), coalesce(sum(rating),0) FROM " + table)
                        .build()));
        List<Field> values = response.records().getFirst();
        long count = longValue(values.get(0));
        long sum = longValue(values.get(1));
        return count == 0 ? 0.0 : (double) sum / count;
    }

    private ExecuteStatementRequest.Builder baseRequest(String sql) {
        return ExecuteStatementRequest.builder()
                .resourceArn(resourceArn)
                .secretArn(secretArn)
                .database(database)
                .sql(sql);
    }

    private static SqlParameter timestampParameter(String name, Instant value) {
        String timestamp = TIMESTAMP_FORMAT.withZone(ZoneOffset.UTC).format(value);
        return SqlParameter.builder()
                .name(name)
                .typeHint(TypeHint.TIMESTAMP)
                .value(Field.builder().stringValue(timestamp).build())
                .build();
    }

    private static SqlParameter stringParameter(String name, String value) {
        return SqlParameter.builder()
                .name(name)
                .value(Field.builder().stringValue(value).build())
                .build();
    }

    private static SqlParameter longParameter(String name, long value) {
        return SqlParameter.builder()
                .name(name)
                .value(Field.builder().longValue(value).build())
                .build();
    }

    private static long longValue(Field field) {
        if (field.longValue() != null) {
            return field.longValue();
        }
        if (field.stringValue() != null) {
            return Long.parseLong(field.stringValue());
        }
        throw new IllegalStateException("Unexpected non-numeric field from the feedback database");
    }

    private static String stringValue(Field field) {
        return Objects.requireNonNull(field.stringValue(), "Expected a string field from the feedback database");
    }

    private static Instant parseTimestamp(String timestamp) {
        return LocalDateTime.parse(timestamp, DATABASE_TIMESTAMP_FORMAT).toInstant(ZoneOffset.UTC);
    }

    private static String required(Map<String, String> environment, String name) {
        String value = environment.get(name);
        if (value == null || value.isBlank()) {
            throw new IllegalStateException("Missing required Lambda environment variable " + name);
        }
        return value;
    }

    private static ExecuteStatementResponse execute(
            Supplier<ExecuteStatementResponse> statement) {
        long deadline = System.nanoTime() + RETRY_WINDOW_NANOS;
        long backoffMillis = INITIAL_BACKOFF_MILLIS;
        while (true) {
            try {
                return statement.get();
            } catch (RuntimeException exception) {
                if (!isRetryable(exception) || System.nanoTime() >= deadline) {
                    throw exception;
                }
                try {
                    Thread.sleep(backoffMillis);
                } catch (InterruptedException interrupted) {
                    Thread.currentThread().interrupt();
                    throw new IllegalStateException("Interrupted while waiting for the feedback database", interrupted);
                }
                backoffMillis = Math.min(backoffMillis * 2, MAX_BACKOFF_MILLIS);
            }
        }
    }

    private static boolean isRetryable(Throwable exception) {
        for (Throwable cause = exception; cause != null; cause = cause.getCause()) {
            if ("DatabaseResumingException".equals(cause.getClass().getSimpleName())
                    || (cause instanceof AwsServiceException serviceException
                    && serviceException.awsErrorDetails() != null
                    && "DatabaseResumingException".equals(serviceException.awsErrorDetails().errorCode()))
                    || (cause.getMessage() != null
                    && cause.getMessage().toLowerCase(Locale.ROOT).contains("communications link failure"))) {
                return true;
            }
        }
        return false;
    }

    private static RdsDataClient client() {
        return ClientHolder.CLIENT;
    }

    private static final class ClientHolder {
        private static final RdsDataClient CLIENT = RdsDataClient.builder()
                .region(Region.of(System.getenv().getOrDefault("AWS_REGION", "us-east-1")))
                .httpClient(UrlConnectionHttpClient.create())
                .build();
    }
}
