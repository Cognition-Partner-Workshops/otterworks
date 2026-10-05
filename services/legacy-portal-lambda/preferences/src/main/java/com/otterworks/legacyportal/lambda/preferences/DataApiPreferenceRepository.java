package com.otterworks.legacyportal.lambda.preferences;

import java.util.List;
import java.util.Optional;
import java.util.regex.Pattern;
import software.amazon.awssdk.http.urlconnection.UrlConnectionHttpClient;
import software.amazon.awssdk.services.rdsdata.RdsDataClient;
import software.amazon.awssdk.services.rdsdata.model.BadRequestException;
import software.amazon.awssdk.services.rdsdata.model.DatabaseUnavailableException;
import software.amazon.awssdk.services.rdsdata.model.ExecuteStatementRequest;
import software.amazon.awssdk.services.rdsdata.model.ExecuteStatementResponse;
import software.amazon.awssdk.services.rdsdata.model.Field;
import software.amazon.awssdk.services.rdsdata.model.SqlParameter;

/** {@link PreferenceRepository} backed by the Aurora Serverless RDS Data API. */
public class DataApiPreferenceRepository implements PreferenceRepository {

    private static final Pattern SCHEMA_NAME = Pattern.compile("^[a-z_][a-z0-9_]*$");
    private static final long RETRY_DEADLINE_MS = 25_000;

    private final RdsDataClient client;
    private final String clusterArn;
    private final String secretArn;
    private final String database;
    private final String schema;

    public DataApiPreferenceRepository() {
        this(
                RdsDataClient.builder().httpClient(UrlConnectionHttpClient.create()).build(),
                requireEnv("CLUSTER_ARN"),
                requireEnv("SECRET_ARN"),
                requireEnv("DB_NAME"),
                requireEnv("DB_SCHEMA"));
    }

    DataApiPreferenceRepository(
            RdsDataClient client,
            String clusterArn,
            String secretArn,
            String database,
            String schema) {
        if (!SCHEMA_NAME.matcher(schema).matches()) {
            throw new IllegalStateException("DB_SCHEMA must match " + SCHEMA_NAME.pattern());
        }
        this.client = client;
        this.clusterArn = clusterArn;
        this.secretArn = secretArn;
        this.database = database;
        this.schema = schema;
    }

    private static String requireEnv(String name) {
        String value = System.getenv(name);
        if (value == null || value.isEmpty()) {
            throw new IllegalStateException("missing environment variable " + name);
        }
        return value;
    }

    @Override
    public Optional<UserPreference> findById(String userId) {
        ExecuteStatementResponse response =
                execute(
                        ExecuteStatementRequest.builder()
                                .resourceArn(clusterArn)
                                .secretArn(secretArn)
                                .database(database)
                                .sql(
                                        "SELECT user_id, theme, locale, email_notifications FROM "
                                                + schema
                                                + ".user_preference WHERE user_id = :userId")
                                .parameters(
                                        SqlParameter.builder()
                                                .name("userId")
                                                .value(Field.builder().stringValue(userId).build())
                                                .build())
                                .build());
        List<List<Field>> records = response.records();
        if (records.isEmpty()) {
            return Optional.empty();
        }
        List<Field> row = records.get(0);
        return Optional.of(
                new UserPreference(
                        row.get(0).stringValue(),
                        row.get(1).stringValue(),
                        row.get(2).stringValue(),
                        row.get(3).booleanValue()));
    }

    @Override
    public UserPreference save(UserPreference preference) {
        execute(
                ExecuteStatementRequest.builder()
                        .resourceArn(clusterArn)
                        .secretArn(secretArn)
                        .database(database)
                        .sql(
                                "INSERT INTO "
                                        + schema
                                        + ".user_preference (user_id, theme, locale, email_notifications) "
                                        + "VALUES (:userId, :theme, :locale, :emailNotifications) "
                                        + "ON CONFLICT (user_id) DO UPDATE SET "
                                        + "theme = EXCLUDED.theme, locale = EXCLUDED.locale, "
                                        + "email_notifications = EXCLUDED.email_notifications")
                        .parameters(
                                SqlParameter.builder()
                                        .name("userId")
                                        .value(
                                                Field.builder()
                                                        .stringValue(preference.getUserId())
                                                        .build())
                                        .build(),
                                SqlParameter.builder()
                                        .name("theme")
                                        .value(
                                                Field.builder()
                                                        .stringValue(preference.getTheme())
                                                        .build())
                                        .build(),
                                SqlParameter.builder()
                                        .name("locale")
                                        .value(
                                                Field.builder()
                                                        .stringValue(preference.getLocale())
                                                        .build())
                                        .build(),
                                SqlParameter.builder()
                                        .name("emailNotifications")
                                        .value(
                                                Field.builder()
                                                        .booleanValue(
                                                                preference.isEmailNotifications())
                                                        .build())
                                        .build())
                        .build());
        return preference;
    }

    /** Retries while the paused cluster resumes (0 ACU), up to ~25 s total. */
    private ExecuteStatementResponse execute(ExecuteStatementRequest request) {
        long deadline = System.currentTimeMillis() + RETRY_DEADLINE_MS;
        long backoff = 500;
        while (true) {
            try {
                return client.executeStatement(request);
            } catch (DatabaseUnavailableException e) {
                if (!retry(deadline)) {
                    throw e;
                }
            } catch (BadRequestException e) {
                String message = e.getMessage() == null ? "" : e.getMessage();
                boolean resuming =
                        message.contains("resuming") || message.contains("is not available");
                if (!resuming || !retry(deadline)) {
                    throw e;
                }
            }
            try {
                Thread.sleep(backoff);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                throw new IllegalStateException("interrupted while waiting for cluster resume", e);
            }
            backoff = Math.min(backoff * 2, 5_000);
        }
    }

    private static boolean retry(long deadline) {
        return System.currentTimeMillis() < deadline;
    }
}
