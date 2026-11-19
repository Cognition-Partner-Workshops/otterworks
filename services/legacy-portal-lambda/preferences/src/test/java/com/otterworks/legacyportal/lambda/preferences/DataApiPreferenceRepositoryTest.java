package com.otterworks.legacyportal.lambda.preferences;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Deque;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.function.Function;
import java.util.stream.Collectors;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.NullSource;
import org.junit.jupiter.params.provider.ValueSource;
import software.amazon.awssdk.services.rdsdata.RdsDataClient;
import software.amazon.awssdk.services.rdsdata.model.BadRequestException;
import software.amazon.awssdk.services.rdsdata.model.DatabaseResumingException;
import software.amazon.awssdk.services.rdsdata.model.ExecuteStatementRequest;
import software.amazon.awssdk.services.rdsdata.model.ExecuteStatementResponse;
import software.amazon.awssdk.services.rdsdata.model.Field;
import software.amazon.awssdk.services.rdsdata.model.SqlParameter;

class DataApiPreferenceRepositoryTest {

    private static final String CLUSTER = "arn:aws:rds:us-east-1:000000000000:cluster:portal";
    private static final String SECRET = "arn:aws:secretsmanager:us-east-1:000000000000:secret:db";

    private FakeRdsDataClient client;
    private DataApiPreferenceRepository repository;

    @BeforeEach
    void setUp() {
        client = new FakeRdsDataClient();
        repository = new DataApiPreferenceRepository(client, CLUSTER, SECRET, "portal", "user_preferences");
    }

    @AfterEach
    void clearInterrupt() {
        Thread.interrupted();
    }

    @ParameterizedTest
    @NullSource
    @ValueSource(
            strings = {
                "",
                "User_Preferences",
                "1schema",
                "public; DROP TABLE x",
                "user_preferences.user_preference",
                "a-b"
            })
    void schemaThatCouldAlterTheSqlIsRejectedAtStartup(String schema) {
        assertThrows(
                IllegalArgumentException.class,
                () -> new DataApiPreferenceRepository(client, CLUSTER, SECRET, "portal", schema));
    }

    @Test
    void findByIdBindsTheUserIdAsAParameterInsteadOfSplicingItIntoSql() {
        String hostile = "x' OR '1'='1";
        client.respond(response());

        repository.findById(hostile);

        ExecuteStatementRequest request = client.requests.get(0);
        assertFalse(request.sql().contains(hostile));
        assertEquals(
                "SELECT user_id, theme, locale, email_notifications FROM"
                        + " user_preferences.user_preference WHERE user_id = :u",
                request.sql());
        assertEquals(Map.of("u", hostile), stringParameters(request));
        assertEquals(CLUSTER, request.resourceArn());
        assertEquals(SECRET, request.secretArn());
        assertEquals("portal", request.database());
    }

    @Test
    void findByIdMapsTheStoredRow() {
        client.respond(
                response(
                        List.of(
                                Field.builder().stringValue("u1").build(),
                                Field.builder().stringValue("dark").build(),
                                Field.builder().stringValue("fr-FR").build(),
                                Field.builder().booleanValue(false).build())));

        assertEquals(
                Optional.of(new UserPreference("u1", "dark", "fr-FR", false)),
                repository.findById("u1"));
    }

    @Test
    void findByIdReturnsEmptyWhenNoRowExists() {
        client.respond(response());
        client.respond(ExecuteStatementResponse.builder().build());

        assertEquals(Optional.empty(), repository.findById("u1"));
        assertEquals(Optional.empty(), repository.findById("u1"));
    }

    @Test
    void saveUpsertsAllFieldsWithBoundParameters() {
        client.respond(ExecuteStatementResponse.builder().numberOfRecordsUpdated(1L).build());
        UserPreference preference = new UserPreference("u1", "dark", "fr-FR", true);

        assertSame(preference, repository.save(preference));

        ExecuteStatementRequest request = client.requests.get(0);
        assertTrue(request.sql().startsWith("INSERT INTO user_preferences.user_preference "));
        assertTrue(request.sql().contains("ON CONFLICT (user_id) DO UPDATE SET"));
        assertEquals(
                Map.of("u", "u1", "t", "dark", "l", "fr-FR"), stringParameters(request));
        SqlParameter email =
                request.parameters().stream().filter(p -> p.name().equals("e")).findFirst().orElseThrow();
        assertEquals(Boolean.TRUE, email.value().booleanValue());
    }

    @Test
    void nonTransientErrorsFailImmediatelyWithoutRetrying() {
        RuntimeException failure = BadRequestException.builder().message("syntax error").build();
        client.fail(failure);

        RuntimeException thrown =
                assertThrows(RuntimeException.class, () -> repository.findById("u1"));

        assertSame(failure, thrown);
        assertEquals(1, client.requests.size());
    }

    @Test
    void auroraResumingIsRetriedUntilTheDatabaseAnswers() {
        client.fail(DatabaseResumingException.builder().message("resuming").build());
        client.respond(response());

        assertEquals(Optional.empty(), repository.findById("u1"));
        assertEquals(2, client.requests.size());
    }

    @Test
    void retriesGiveUpAfterFiveAttemptsAndSurfaceTheError() {
        DatabaseResumingException failure =
                DatabaseResumingException.builder().message("resuming").build();
        for (int i = 0; i < 6; i++) {
            client.fail(failure);
        }

        RuntimeException thrown =
                assertThrows(
                        RuntimeException.class,
                        () -> repository.save(new UserPreference("u1", "dark", "fr-FR", true)));

        assertSame(failure, thrown);
        assertEquals(5, client.requests.size());
    }

    // An interrupted thread makes the retry sleep fail at once, so these classify an error as
    // retryable (IllegalStateException from the sleep) or not (the original error) without waiting.

    @Test
    void wrappedCommunicationsFailureIsTreatedAsTransient() {
        client.fail(
                new RuntimeException(
                        "wrapper", new RuntimeException("Communications link failure")));
        Thread.currentThread().interrupt();

        IllegalStateException thrown =
                assertThrows(IllegalStateException.class, () -> repository.findById("u1"));

        assertTrue(thrown.getMessage().contains("Interrupted"));
        assertTrue(Thread.currentThread().isInterrupted());
        assertEquals(1, client.requests.size());
    }

    @Test
    void databaseNotAvailableMessageIsTreatedAsTransient() {
        client.fail(new RuntimeException("Database portal is not available"));
        Thread.currentThread().interrupt();

        assertThrows(IllegalStateException.class, () -> repository.findById("u1"));
    }

    @Test
    void errorWithoutMessageIsNotRetried() {
        RuntimeException failure = new RuntimeException((String) null);
        client.fail(failure);
        Thread.currentThread().interrupt();

        assertSame(failure, assertThrows(RuntimeException.class, () -> repository.findById("u1")));
    }

    private static ExecuteStatementResponse response(List<Field>... rows) {
        return ExecuteStatementResponse.builder().records(List.of(rows)).build();
    }

    private static Map<String, String> stringParameters(ExecuteStatementRequest request) {
        return request.parameters().stream()
                .filter(p -> p.value().stringValue() != null)
                .collect(Collectors.toMap(SqlParameter::name, p -> p.value().stringValue()));
    }

    private static final class FakeRdsDataClient implements RdsDataClient {
        final List<ExecuteStatementRequest> requests = new ArrayList<>();
        private final Deque<Function<ExecuteStatementRequest, ExecuteStatementResponse>> outcomes =
                new ArrayDeque<>();

        void respond(ExecuteStatementResponse response) {
            outcomes.add(request -> response);
        }

        void fail(RuntimeException failure) {
            outcomes.add(
                    request -> {
                        throw failure;
                    });
        }

        @Override
        public ExecuteStatementResponse executeStatement(ExecuteStatementRequest request) {
            requests.add(request);
            return outcomes.removeFirst().apply(request);
        }

        @Override
        public String serviceName() {
            return "rds-data";
        }

        @Override
        public void close() {}
    }
}
