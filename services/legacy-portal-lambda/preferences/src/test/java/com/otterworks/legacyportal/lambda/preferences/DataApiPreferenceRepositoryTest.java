package com.otterworks.legacyportal.lambda.preferences;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.otterworks.legacyportal.lambda.preferences.DataApiTestSupport.BlackHole;
import com.otterworks.legacyportal.lambda.preferences.DataApiTestSupport.FakeClock;
import com.otterworks.legacyportal.lambda.preferences.DataApiTestSupport.ScriptedClient;
import java.time.Duration;
import java.util.HashSet;
import java.util.List;
import java.util.Optional;
import java.util.Set;
import org.junit.jupiter.api.Test;
import software.amazon.awssdk.core.client.config.ClientOverrideConfiguration;
import software.amazon.awssdk.core.exception.SdkClientException;
import software.amazon.awssdk.services.rdsdata.RdsDataClient;
import software.amazon.awssdk.services.rdsdata.model.DatabaseResumingException;
import software.amazon.awssdk.services.rdsdata.model.ExecuteStatementResponse;

class DataApiPreferenceRepositoryTest {

    private static final long LAMBDA_TIMEOUT_MILLIS = 29_000;

    static DatabaseResumingException resuming() {
        return DatabaseResumingException.builder().message("resuming").build();
    }

    static ExecuteStatementResponse empty() {
        return ExecuteStatementResponse.builder().records(List.of()).build();
    }

    static DataApiPreferenceRepository repo(ScriptedClient client, FakeClock clock) {
        return new DataApiPreferenceRepository(client, "arn:cluster", "arn:secret", "db", "preferences", clock);
    }

    @Test
    void resumingClusterIsRetriedUntilWarm() {
        FakeClock clock = new FakeClock();
        ScriptedClient client = new ScriptedClient()
                .then(() -> { throw resuming(); })
                .then(() -> { throw SdkClientException.create("Communications link failure"); })
                .then(DataApiPreferenceRepositoryTest::empty);

        assertEquals(Optional.empty(), repo(client, clock).findById("u1"));
        assertEquals(3, client.requests.size());
    }

    @Test
    void retriesAreBoundedByTheWindowNotByAFixedFiveSecondPause() {
        FakeClock clock = new FakeClock();
        ScriptedClient client = new ScriptedClient().then(() -> { throw resuming(); });

        assertThrows(DatabaseResumingException.class, () -> repo(client, clock).findById("u1"));
        assertEquals(DataApiPreferenceRepository.RETRY_WINDOW_NANOS, clock.now);
        assertTrue(clock.sleeps.get(0) < 5_000_000_000L, "first pause " + clock.sleeps.get(0) + " ns");
        assertTrue(clock.sleeps.stream().allMatch(s -> s <= DataApiPreferenceRepository.MAX_DELAY_MILLIS * 1_000_000L));
        long worstCaseMillis = clock.now / 1_000_000L + DataApiPreferenceRepository.API_CALL_TIMEOUT.toMillis();
        assertTrue(worstCaseMillis < LAMBDA_TIMEOUT_MILLIS, "window + one call = " + worstCaseMillis + " ms");
    }

    @Test
    void nonTransientFailuresAreNotRetried() {
        FakeClock clock = new FakeClock();
        ScriptedClient client = new ScriptedClient()
                .then(() -> { throw new IllegalArgumentException("syntax error"); });

        assertThrows(IllegalArgumentException.class, () -> repo(client, clock).findById("u1"));
        assertEquals(1, client.requests.size());
    }

    @Test
    void backoffIsJitteredAndCapped() {
        Set<Long> seen = new HashSet<>();
        for (int i = 0; i < 200; i++) {
            long d = DataApiPreferenceRepository.backoffMillis(10);
            assertTrue(d >= 1_500 && d <= DataApiPreferenceRepository.MAX_DELAY_MILLIS, "delay " + d);
            seen.add(d);
        }
        assertTrue(seen.size() > 1, "delays must vary between callers");
    }

    @Test
    void clientHasATotalDeadlineAndNoRetriedAttemptTimeout() {
        ClientOverrideConfiguration c = DataApiPreferenceRepository.clientOverrides();
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
            assertTrue(elapsed < DataApiPreferenceRepository.API_CALL_TIMEOUT.toMillis() + 2_000,
                    "took " + elapsed + " ms");
        }
    }
}
