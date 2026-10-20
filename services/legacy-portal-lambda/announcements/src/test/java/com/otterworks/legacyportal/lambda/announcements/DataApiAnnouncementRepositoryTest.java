package com.otterworks.legacyportal.lambda.announcements;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.time.Duration;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

import org.junit.jupiter.api.Test;

import com.otterworks.legacyportal.lambda.announcements.DataApiTestSupport.BlackHole;
import com.otterworks.legacyportal.lambda.announcements.DataApiTestSupport.FakeClock;
import com.otterworks.legacyportal.lambda.announcements.DataApiTestSupport.ScriptedClient;

import software.amazon.awssdk.core.client.config.ClientOverrideConfiguration;
import software.amazon.awssdk.core.exception.SdkClientException;
import software.amazon.awssdk.services.rdsdata.RdsDataClient;
import software.amazon.awssdk.services.rdsdata.model.DatabaseResumingException;
import software.amazon.awssdk.services.rdsdata.model.ExecuteStatementResponse;

class DataApiAnnouncementRepositoryTest {

    private static final long LAMBDA_TIMEOUT_MILLIS = 29_000;

    static DatabaseResumingException resuming() {
        return DatabaseResumingException.builder().message("resuming").build();
    }

    static ExecuteStatementResponse empty() {
        return ExecuteStatementResponse.builder().records(List.of()).build();
    }

    static DataApiAnnouncementRepository repo(ScriptedClient client, FakeClock clock) {
        return new DataApiAnnouncementRepository(client, "arn:cluster", "arn:secret", "db", "announcements", clock);
    }

    @Test
    void resumingClusterIsRetriedUntilWarm() {
        FakeClock clock = new FakeClock();
        ScriptedClient client = new ScriptedClient()
                .then(() -> { throw resuming(); })
                .then(() -> { throw resuming(); })
                .then(DataApiAnnouncementRepositoryTest::empty);

        assertEquals(List.of(), repo(client, clock).findAll());
        assertEquals(3, client.requests.size());
    }

    @Test
    void resumeRetriesStopAtTheWindowWithoutOversleeping() {
        FakeClock clock = new FakeClock();
        ScriptedClient client = new ScriptedClient().then(() -> { throw resuming(); });

        assertThrows(DatabaseResumingException.class, () -> repo(client, clock).findAll());
        assertEquals(DataApiAnnouncementRepository.RETRY_WINDOW_NANOS, clock.now,
                "last pause is clipped to the window so the final attempt starts inside it");
        long worstCaseMillis = clock.now / 1_000_000L + DataApiAnnouncementRepository.API_CALL_TIMEOUT.toMillis();
        assertTrue(worstCaseMillis < LAMBDA_TIMEOUT_MILLIS, "window + one call = " + worstCaseMillis + " ms");
    }

    @Test
    void otherFailuresAreNotRetried() {
        FakeClock clock = new FakeClock();
        ScriptedClient client = new ScriptedClient()
                .then(() -> { throw SdkClientException.create("Communications link failure"); });

        assertThrows(SdkClientException.class, () -> repo(client, clock).findAll());
        assertEquals(1, client.requests.size());
        assertEquals(0, clock.now);
    }

    @Test
    void backoffIsJitteredAndCapped() {
        Set<Long> seen = new HashSet<>();
        for (int i = 0; i < 200; i++) {
            long d = DataApiAnnouncementRepository.backoffMillis(10);
            assertTrue(d >= 1_500 && d <= DataApiAnnouncementRepository.MAX_DELAY_MILLIS, "delay " + d);
            seen.add(d);
        }
        assertTrue(seen.size() > 1, "delays must vary between callers");
    }

    @Test
    void clientHasATotalDeadlineAndNoRetriedAttemptTimeout() {
        ClientOverrideConfiguration c = DataApiAnnouncementRepository.clientOverrides();
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
            assertTrue(elapsed < DataApiAnnouncementRepository.API_CALL_TIMEOUT.toMillis() + 2_000,
                    "took " + elapsed + " ms");
        }
    }
}
