package com.otterworks.legacyportal.lambda.preferences;

import java.util.List;
import java.util.Optional;
import java.util.function.Supplier;
import java.util.regex.Pattern;
import software.amazon.awssdk.http.urlconnection.UrlConnectionHttpClient;
import software.amazon.awssdk.services.rdsdata.RdsDataClient;
import software.amazon.awssdk.services.rdsdata.model.DatabaseResumingException;
import software.amazon.awssdk.services.rdsdata.model.ExecuteStatementRequest;
import software.amazon.awssdk.services.rdsdata.model.ExecuteStatementResponse;
import software.amazon.awssdk.services.rdsdata.model.Field;
import software.amazon.awssdk.services.rdsdata.model.SqlParameter;

public final class DataApiPreferenceRepository implements PreferenceRepository {

    private static final Pattern VALID_SCHEMA = Pattern.compile("[a-z_][a-z0-9_]*");
    private static final int MAX_ATTEMPTS = 5;
    private static final long RETRY_DELAY_MILLIS = 5_000;

    private final RdsDataClient client;
    private final String resourceArn;
    private final String secretArn;
    private final String database;
    private final String table;

    public DataApiPreferenceRepository(
            RdsDataClient client,
            String resourceArn,
            String secretArn,
            String database,
            String schema) {
        if (schema == null || !VALID_SCHEMA.matcher(schema).matches()) {
            throw new IllegalArgumentException("DB_SCHEMA must match [a-z_][a-z0-9_]*");
        }
        this.client = client;
        this.resourceArn = resourceArn;
        this.secretArn = secretArn;
        this.database = database;
        this.table = schema + ".user_preference";
    }

    public static DataApiPreferenceRepository fromEnvironment() {
        RdsDataClient client =
                RdsDataClient.builder()
                        .httpClientBuilder(UrlConnectionHttpClient.builder())
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

    private ExecuteStatementResponse execute(
            Supplier<ExecuteStatementResponse> operation) {
        for (int attempt = 1; ; attempt++) {
            try {
                return operation.get();
            } catch (RuntimeException exception) {
                if (attempt >= MAX_ATTEMPTS || !isRetryable(exception)) {
                    throw exception;
                }
                try {
                    Thread.sleep(RETRY_DELAY_MILLIS);
                } catch (InterruptedException interrupted) {
                    Thread.currentThread().interrupt();
                    throw new IllegalStateException("Interrupted while waiting for database", interrupted);
                }
            }
        }
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
