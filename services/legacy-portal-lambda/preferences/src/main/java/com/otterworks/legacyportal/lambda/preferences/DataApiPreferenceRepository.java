package com.otterworks.legacyportal.lambda.preferences;

import java.time.Duration;
import java.util.List;
import java.util.Optional;
import java.util.concurrent.ThreadLocalRandom;
import java.util.function.Supplier;
import java.util.regex.Pattern;
import software.amazon.awssdk.core.client.config.ClientOverrideConfiguration;
import software.amazon.awssdk.http.urlconnection.UrlConnectionHttpClient;
import software.amazon.awssdk.services.rdsdata.RdsDataClient;
import software.amazon.awssdk.services.rdsdata.model.DatabaseResumingException;
import software.amazon.awssdk.services.rdsdata.model.ExecuteStatementRequest;
import software.amazon.awssdk.services.rdsdata.model.ExecuteStatementResponse;
import software.amazon.awssdk.services.rdsdata.model.Field;
import software.amazon.awssdk.services.rdsdata.model.SqlParameter;

public final class DataApiPreferenceRepository implements PreferenceRepository {

    private static final Pattern VALID_SCHEMA = Pattern.compile("[a-z_][a-z0-9_]*");
    // Retry window for a paused cluster plus one call must stay under the 29 s Lambda timeout.
    static final long RETRY_WINDOW_NANOS = 20_000_000_000L;
    static final Duration API_CALL_TIMEOUT = Duration.ofSeconds(8);
    static final long BASE_DELAY_MILLIS = 250;
    static final long MAX_DELAY_MILLIS = 3_000;

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
    private final String resourceArn;
    private final String secretArn;
    private final String database;
    private final String table;
    private final RetryClock clock;

    public DataApiPreferenceRepository(
            RdsDataClient client,
            String resourceArn,
            String secretArn,
            String database,
            String schema) {
        this(client, resourceArn, secretArn, database, schema, SYSTEM_CLOCK);
    }

    DataApiPreferenceRepository(
            RdsDataClient client,
            String resourceArn,
            String secretArn,
            String database,
            String schema,
            RetryClock clock) {
        if (schema == null || !VALID_SCHEMA.matcher(schema).matches()) {
            throw new IllegalArgumentException("DB_SCHEMA must match [a-z_][a-z0-9_]*");
        }
        this.client = client;
        this.resourceArn = resourceArn;
        this.secretArn = secretArn;
        this.database = database;
        this.table = schema + ".user_preference";
        this.clock = clock;
    }

    /**
     * Total deadline per ExecuteStatement including SDK retries. No per-attempt timeout, so the
     * SDK does not add retries of its own on a slow statement.
     */
    static ClientOverrideConfiguration clientOverrides() {
        return ClientOverrideConfiguration.builder().apiCallTimeout(API_CALL_TIMEOUT).build();
    }

    public static DataApiPreferenceRepository fromEnvironment() {
        RdsDataClient client =
                RdsDataClient.builder()
                        .httpClientBuilder(UrlConnectionHttpClient.builder())
                        .overrideConfiguration(clientOverrides())
                        .build();
        return new DataApiPreferenceRepository(
                client,
                requiredEnvironment("CLUSTER_ARN"),
                requiredEnvironment("SECRET_ARN"),
                requiredEnvironment("DB_NAME"),
                requiredEnvironment("DB_SCHEMA"));
    }

    @Override
    public Optional<UserPreference> findById(String userId) {
        String sql =
                "SELECT user_id, theme, locale, email_notifications FROM "
                        + table
                        + " WHERE user_id = :u";
        ExecuteStatementResponse response =
                execute(
                        () ->
                                client.executeStatement(
                                        baseRequest(sql)
                                                .parameters(stringParameter("u", userId))
                                                .build()));
        if (response.records() == null || response.records().isEmpty()) {
            return Optional.empty();
        }
        List<Field> row = response.records().getFirst();
        return Optional.of(
                new UserPreference(
                        row.get(0).stringValue(),
                        row.get(1).stringValue(),
                        row.get(2).stringValue(),
                        row.get(3).booleanValue()));
    }

    @Override
    public UserPreference save(UserPreference preference) {
        String sql =
                "INSERT INTO "
                        + table
                        + " (user_id, theme, locale, email_notifications)"
                        + " VALUES (:u, :t, :l, :e)"
                        + " ON CONFLICT (user_id) DO UPDATE SET"
                        + " theme=EXCLUDED.theme, locale=EXCLUDED.locale,"
                        + " email_notifications=EXCLUDED.email_notifications";
        execute(
                () ->
                        client.executeStatement(
                                baseRequest(sql)
                                        .parameters(
                                                stringParameter("u", preference.userId()),
                                                stringParameter("t", preference.theme()),
                                                stringParameter("l", preference.locale()),
                                                SqlParameter.builder()
                                                        .name("e")
                                                        .value(
                                                                Field.builder()
                                                                        .booleanValue(
                                                                                preference
                                                                                        .emailNotifications())
                                                                        .build())
                                                        .build())
                                        .build()));
        return preference;
    }

    private ExecuteStatementRequest.Builder baseRequest(String sql) {
        return ExecuteStatementRequest.builder()
                .resourceArn(resourceArn)
                .secretArn(secretArn)
                .database(database)
                .sql(sql);
    }

    private SqlParameter stringParameter(String name, String value) {
        return SqlParameter.builder()
                .name(name)
                .value(Field.builder().stringValue(value).build())
                .build();
    }

    // Reads and the idempotent upsert are both safe to repeat.
    private ExecuteStatementResponse execute(
            Supplier<ExecuteStatementResponse> operation) {
        long started = clock.nanoTime();
        for (int attempt = 1; ; attempt++) {
            try {
                return operation.get();
            } catch (RuntimeException exception) {
                long remaining = RETRY_WINDOW_NANOS - (clock.nanoTime() - started);
                if (remaining <= 0 || !isRetryable(exception)) {
                    throw exception;
                }
                try {
                    clock.sleep(Math.min(remaining, backoffMillis(attempt) * 1_000_000L));
                } catch (InterruptedException interrupted) {
                    Thread.currentThread().interrupt();
                    throw new IllegalStateException("Interrupted while waiting for database", interrupted);
                }
            }
        }
    }

    /** Capped exponential backoff with equal jitter. */
    static long backoffMillis(int attempt) {
        long ceiling = Math.min(MAX_DELAY_MILLIS, BASE_DELAY_MILLIS << Math.min(attempt - 1, 20));
        return ceiling / 2 + ThreadLocalRandom.current().nextLong(ceiling / 2 + 1);
    }

    private boolean isRetryable(Throwable exception) {
        for (Throwable current = exception; current != null; current = current.getCause()) {
            if (current instanceof DatabaseResumingException) {
                return true;
            }
            String message = current.getMessage();
            if (message != null
                    && (message.contains("is not available")
                            || message.contains("Communications link failure"))) {
                return true;
            }
        }
        return false;
    }

    private static String requiredEnvironment(String name) {
        String value = System.getenv(name);
        if (value == null || value.isBlank()) {
            throw new IllegalStateException("Missing environment variable " + name);
        }
        return value;
    }
}
