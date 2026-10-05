package com.otterworks.legacyportal.lambda.announcements;

import java.time.Duration;
import java.time.Instant;
import java.time.LocalDateTime;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.time.format.DateTimeFormatterBuilder;
import java.time.temporal.ChronoField;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Optional;
import java.util.regex.Pattern;
import software.amazon.awssdk.core.client.config.ClientOverrideConfiguration;
import software.amazon.awssdk.core.retry.RetryPolicy;
import software.amazon.awssdk.http.urlconnection.UrlConnectionHttpClient;
import software.amazon.awssdk.services.rdsdata.RdsDataClient;
import software.amazon.awssdk.services.rdsdata.model.ExecuteStatementRequest;
import software.amazon.awssdk.services.rdsdata.model.ExecuteStatementResponse;
import software.amazon.awssdk.services.rdsdata.model.Field;
import software.amazon.awssdk.services.rdsdata.model.RdsDataException;
import software.amazon.awssdk.services.rdsdata.model.SqlParameter;

public final class DataApiAnnouncementRepository implements AnnouncementRepository {
    private static final Pattern SAFE_SCHEMA = Pattern.compile("[A-Za-z_][A-Za-z0-9_]*");
    private static final DateTimeFormatter TIMESTAMP_PARAMETER =
            DateTimeFormatter.ofPattern("uuuu-MM-dd HH:mm:ss.SSSSSS", Locale.ROOT);
    private static final DateTimeFormatter TIMESTAMP_RESULT =
            new DateTimeFormatterBuilder()
                    .appendPattern("uuuu-MM-dd HH:mm:ss")
                    .optionalStart()
                    .appendFraction(ChronoField.NANO_OF_SECOND, 0, 9, true)
                    .optionalEnd()
                    .toFormatter(Locale.ROOT);
    private static final long RETRY_WINDOW_NANOS = Duration.ofSeconds(20).toNanos();
    private static final long RETRY_DELAY_MILLIS = 1_000;

    private final String resourceArn;
    private final String secretArn;
    private final String database;
    private final String schema;

    public DataApiAnnouncementRepository() {
        this(System.getenv());
    }

    DataApiAnnouncementRepository(java.util.Map<String, String> environment) {
        this.resourceArn = required(environment, "CLUSTER_ARN");
        this.secretArn = required(environment, "SECRET_ARN");
        this.database = required(environment, "DB_NAME");
        this.schema = required(environment, "DB_SCHEMA");
        if (!SAFE_SCHEMA.matcher(schema).matches()) {
            throw new IllegalArgumentException("DB_SCHEMA must be a valid SQL schema identifier");
        }
    }

    @Override
    public Announcement save(Announcement announcement) {
        if (announcement.getId() == null) {
            return insert(announcement);
        }
        String sql = "UPDATE " + schema + ".announcement SET title = :title, body = :body, "
                + "published = :published WHERE id = :id "
                + "RETURNING id, title, body, published, created_at";
        List<List<Field>> records = execute(
                sql,
                parameter("title", announcement.getTitle()),
                parameter("body", announcement.getBody()),
                parameter("published", announcement.isPublished()),
                parameter("id", announcement.getId()));
        if (records.isEmpty()) {
            throw notFound(announcement.getId());
        }
        return map(records.get(0));
    }

    @Override
    public Announcement insert(Announcement announcement) {
        Instant createdAt = announcement.getCreatedAt().truncatedTo(ChronoUnit.MICROS);
        String sql = "INSERT INTO " + schema
                + ".announcement (title, body, published, created_at) "
                + "VALUES (:title, :body, :published, :createdAt) RETURNING id";
        List<List<Field>> records = execute(
                sql,
                parameter("title", announcement.getTitle()),
                parameter("body", announcement.getBody()),
                parameter("published", announcement.isPublished()),
                timestampParameter("createdAt", createdAt));
        if (records.isEmpty()) {
            throw new IllegalStateException("Announcement insert did not return an id");
        }
        return new Announcement(
                records.get(0).get(0).longValue(),
                announcement.getTitle(),
                announcement.getBody(),
                announcement.isPublished(),
                createdAt);
    }

    @Override
    public Optional<Announcement> findById(Long id) {
        List<List<Field>> records = execute(
                selectColumns() + " WHERE id = :id",
                parameter("id", id));
        return records.isEmpty() ? Optional.empty() : Optional.of(map(records.get(0)));
    }

    @Override
    public List<Announcement> findAll() {
        return mapAll(execute(selectColumns(), List.of()));
    }

    @Override
    public List<Announcement> findByPublishedTrueOrderByCreatedAtDesc() {
        return mapAll(execute(selectColumns() + " WHERE published = true ORDER BY created_at DESC", List.of()));
    }

    @Override
    public Announcement updatePublished(Long id, boolean published) {
        String sql = "UPDATE " + schema + ".announcement SET published = :published WHERE id = :id "
                + "RETURNING id, title, body, published, created_at";
        List<List<Field>> records = execute(sql, parameter("published", published), parameter("id", id));
        if (records.isEmpty()) {
            throw notFound(id);
        }
        return map(records.get(0));
    }

    private String selectColumns() {
        return "SELECT id, title, body, published, created_at FROM " + schema + ".announcement";
    }

    private List<List<Field>> execute(String sql, List<SqlParameter> parameters) {
        return executeWithResumeRetry(sql, parameters).records();
    }

    private List<List<Field>> execute(String sql, SqlParameter... parameters) {
        return execute(sql, List.of(parameters));
    }

    private ExecuteStatementResponse executeWithResumeRetry(String sql, List<SqlParameter> parameters) {
        long deadline = System.nanoTime() + RETRY_WINDOW_NANOS;
        while (true) {
            try {
                return client().executeStatement(
                        ExecuteStatementRequest.builder()
                                .resourceArn(resourceArn)
                                .secretArn(secretArn)
                                .database(database)
                                .sql(sql)
                                .parameters(parameters)
                                .build());
            } catch (RdsDataException exception) {
                if (!isDatabaseResuming(exception) || System.nanoTime() >= deadline) {
                    throw exception;
                }
                long remainingMillis = (deadline - System.nanoTime()) / 1_000_000;
                if (remainingMillis <= 0) {
                    throw exception;
                }
                try {
                    Thread.sleep(Math.min(RETRY_DELAY_MILLIS, remainingMillis));
                } catch (InterruptedException interrupted) {
                    Thread.currentThread().interrupt();
                    throw exception;
                }
            }
        }
    }

    private static boolean isDatabaseResuming(RdsDataException exception) {
        return exception.awsErrorDetails() != null
                && "DatabaseResumingException".equals(exception.awsErrorDetails().errorCode());
    }

    private static RdsDataClient client() {
        return ClientHolder.CLIENT;
    }

    private static List<Announcement> mapAll(List<List<Field>> records) {
        List<Announcement> announcements = new ArrayList<>(records.size());
        for (List<Field> record : records) {
            announcements.add(map(record));
        }
        return announcements;
    }

    private static Announcement map(List<Field> fields) {
        return new Announcement(
                fields.get(0).longValue(),
                fields.get(1).stringValue(),
                fields.get(2).stringValue(),
                fields.get(3).booleanValue(),
                parseTimestamp(fields.get(4).stringValue()));
    }

    private static Instant parseTimestamp(String value) {
        if (value.endsWith("Z")) {
            return Instant.parse(value);
        }
        if (value.indexOf('T') >= 0 && (value.indexOf('+') >= 0 || value.lastIndexOf('-') > 9)) {
            return OffsetDateTime.parse(value).toInstant();
        }
        return LocalDateTime.parse(value, TIMESTAMP_RESULT).toInstant(ZoneOffset.UTC);
    }

    private static SqlParameter parameter(String name, String value) {
        return SqlParameter.builder()
                .name(name)
                .value(Field.builder().stringValue(value).build())
                .build();
    }

    private static SqlParameter parameter(String name, Long value) {
        return SqlParameter.builder()
                .name(name)
                .value(Field.builder().longValue(value).build())
                .build();
    }

    private static SqlParameter parameter(String name, boolean value) {
        return SqlParameter.builder()
                .name(name)
                .value(Field.builder().booleanValue(value).build())
                .build();
    }

    private static SqlParameter timestampParameter(String name, Instant value) {
        LocalDateTime utc = LocalDateTime.ofInstant(value, ZoneOffset.UTC);
        return SqlParameter.builder()
                .name(name)
                .typeHint("TIMESTAMP")
                .value(Field.builder().stringValue(TIMESTAMP_PARAMETER.format(utc)).build())
                .build();
    }

    private static String required(java.util.Map<String, String> environment, String name) {
        String value = environment.get(name);
        if (value == null || value.isBlank()) {
            throw new IllegalStateException("Missing required environment variable " + name);
        }
        return value;
    }

    private static java.util.NoSuchElementException notFound(Long id) {
        return new java.util.NoSuchElementException("announcement " + id + " not found");
    }

    private static final class ClientHolder {
        private static final RdsDataClient CLIENT = RdsDataClient.builder()
                .httpClientBuilder(UrlConnectionHttpClient.builder())
                .overrideConfiguration(ClientOverrideConfiguration.builder()
                        .apiCallTimeout(Duration.ofSeconds(2))
                        .apiCallAttemptTimeout(Duration.ofSeconds(2))
                        .retryPolicy(RetryPolicy.none())
                        .build())
                .build();
    }
}
