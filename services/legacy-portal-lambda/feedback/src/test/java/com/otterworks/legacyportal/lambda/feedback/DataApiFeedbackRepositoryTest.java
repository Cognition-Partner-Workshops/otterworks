package com.otterworks.legacyportal.lambda.feedback;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.otterworks.legacyportal.lambda.feedback.DataApiTestSupport.BlackHole;
import com.otterworks.legacyportal.lambda.feedback.DataApiTestSupport.FakeClock;
import com.otterworks.legacyportal.lambda.feedback.DataApiTestSupport.ScriptedClient;
import java.time.Duration;
import java.time.Instant;
import java.util.List;
import org.junit.jupiter.api.Test;
import software.amazon.awssdk.core.client.config.ClientOverrideConfiguration;
import software.amazon.awssdk.core.exception.SdkClientException;
import software.amazon.awssdk.services.rdsdata.RdsDataClient;
import software.amazon.awssdk.services.rdsdata.model.ExecuteStatementResponse;
import software.amazon.awssdk.services.rdsdata.model.Field;

class DataApiFeedbackRepositoryTest {

    private static final long LAMBDA_TIMEOUT_MILLIS = 29_000;
    private static final Feedback NEW_FEEDBACK =
            new Feedback(null, "u1", 5, "great", Instant.parse("2026-10-06T08:00:00Z"));

    /** The pinned SDK predates the modelled exception; the repository matches it by simple name. */
    static final class DatabaseResumingException extends RuntimeException {
        DatabaseResumingException() {
            super("resuming");
        }
    }

    static DatabaseResumingException resuming() {
        return new DatabaseResumingException();
    }

    static ExecuteStatementResponse id(long id) {
        return ExecuteStatementResponse.builder()
                .records(List.of(List.of(Field.builder().longValue(id).build()))).build();
    }

    static DataApiFeedbackRepository repo(ScriptedClient client, FakeClock clock) {
        return new DataApiFeedbackRepository(client, "arn:cluster", "arn:secret", "db", "feedback", clock);
    }

    @Test
    void insertWithUnknownOutcomeIsNotRepeated() {
        ScriptedClient client = new ScriptedClient()
                .then(() -> { throw SdkClientException.create("Communications link failure"); })
                .then(() -> id(2));

        assertThrows(SdkClientException.class, () -> repo(client, new FakeClock()).save(NEW_FEEDBACK));
        assertEquals(1, client.requests.size(), "a second INSERT could store the feedback twice");
    }

    @Test
    void insertIsRetriedWhileTheClusterResumes() {
        ScriptedClient client = new ScriptedClient()
                .then(() -> { throw resuming(); })
                .then(() -> id(7));

        assertEquals(7L, repo(client, new FakeClock()).save(NEW_FEEDBACK).id());
        assertEquals(2, client.requests.size());
    }

    @Test
    void readsStillRetryALostConnection() {
        ScriptedClient client = new ScriptedClient()
                .then(() -> { throw SdkClientException.create("Communications link failure"); })
                .then(() -> ExecuteStatementResponse.builder().records(List.of()).build());

        assertEquals(List.of(), repo(client, new FakeClock()).findByUserId("u1"));
        assertEquals(2, client.requests.size());
    }

    @Test
    void retriesStopAtTheWindowWithJitteredCappedPauses() {
        FakeClock clock = new FakeClock();
        ScriptedClient client = new ScriptedClient().then(() -> { throw resuming(); });

        assertThrows(DatabaseResumingException.class, () -> repo(client, clock).findByUserId("u1"));
        assertEquals(DataApiFeedbackRepository.RETRY_WINDOW_NANOS, clock.now);
        assertTrue(clock.sleeps.stream().allMatch(s -> s <= DataApiFeedbackRepository.MAX_DELAY_MILLIS * 1_000_000L));
        assertTrue(clock.sleeps.get(0) >= 125_000_000L && clock.sleeps.get(0) <= 250_000_000L,
                "first pause " + clock.sleeps.get(0));
        long worstCaseMillis = clock.now / 1_000_000L + DataApiFeedbackRepository.API_CALL_TIMEOUT.toMillis();
        assertTrue(worstCaseMillis < LAMBDA_TIMEOUT_MILLIS, "window + one call = " + worstCaseMillis + " ms");
    }

    @Test
    void clientHasATotalDeadlineAndNoRetriedAttemptTimeout() {
        ClientOverrideConfiguration c = DataApiFeedbackRepository.clientOverrides();
        assertEquals(Duration.ofSeconds(8), c.apiCallTimeout().orElseThrow());
        assertFalse(c.apiCallAttemptTimeout().isPresent());
    }

    @Test
    void hungDataApiCallFailsWithinTheDeadline() throws Exception {
        try (BlackHole hole = new BlackHole();
                RdsDataClient client = DataApiTestSupport.productionConfiguredClient(hole.uri())) {
            long t0 = System.nanoTime();
            assertThrows(RuntimeException.class, () -> client.executeStatement(
                    b -> b.resourceArn("arn:cluster").secretArn("arn:secret").sql("SELECT 1")));
            long elapsed = (System.nanoTime() - t0) / 1_000_000L;
            assertTrue(elapsed < DataApiFeedbackRepository.API_CALL_TIMEOUT.toMillis() + 2_000,
                    "took " + elapsed + " ms");
        }
    }
}
