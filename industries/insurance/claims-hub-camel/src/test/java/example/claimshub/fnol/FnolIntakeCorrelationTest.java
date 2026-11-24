package example.claimshub.fnol;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.InputStream;
import java.math.BigDecimal;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.util.Map;

import org.apache.camel.Exchange;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.yaml.snakeyaml.Yaml;

/**
 * ClaimNumberCorrelation and the Listen_Correction shape: an activating receive, then whichever comes first of
 * a correlated receive (the correction) or the correction window delay.
 */
@DisplayName("FnolIntake correlation on ClaimNumber")
class FnolIntakeCorrelationTest extends FnolIntakeTestBase {

    private static final String CLAIM = "CLM-2026-100404";
    private static final String OTHER_CLAIM = "CLM-2026-100409";
    private static final String CORRECTED_AMOUNT = "3875.00";

    private final String original = read(fixture("corpus/inputs/fnol/" + CLAIM + ".xml"));
    private final String correction = original
            .replaceFirst("<EstimatedLossAmt>[^<]*</EstimatedLossAmt>", "<EstimatedLossAmt>" + CORRECTED_AMOUNT + "</EstimatedLossAmt>")
            .replaceFirst("</IncidentDesc>", " (corrected by agency)</IncidentDesc>");

    @BeforeEach
    void clean() throws Exception {
        reset();
        assertThat(correction).isNotEqualTo(original).contains(CORRECTED_AMOUNT);
    }

    @Test
    @DisplayName("a single FNOL waits out the correction window (Delay_CorrectionWindow) before it is processed")
    void singleFnolWaitsOutTheWindow() throws Exception {
        send(original);
        Thread.sleep(WINDOW.minusMillis(1500).toMillis());
        assertThat(completed().getReceivedCounter()).as("instance finished before the correction window elapsed").isZero();
        assertThat(LegacySystems.claims()).as("claim inserted before the correction window elapsed").isEmpty();

        awaitCompleted(1, WINDOW.plusSeconds(10));
        Exchange instance = completed().getExchanges().get(0);
        assertThat(claimNumber(instance)).isEqualTo(CLAIM);
        assertThat(instance.getProperty("msgClaim", String.class)).doesNotContain(CORRECTED_AMOUNT);
        assertThat(LegacySystems.claims()).extracting(LegacySystems.ClaimRow::claimNumber).containsExactly(CLAIM);
    }

    @Test
    @DisplayName("a second FNOL for the same claim inside the window replaces the first, and ends the wait")
    void correctionInsideWindowReplacesFirst() throws Exception {
        long start = System.nanoTime();
        send(original);
        Thread.sleep(1000);
        send(correction);

        awaitCompleted(1, WINDOW.plusSeconds(10));
        Duration took = Duration.ofNanos(System.nanoTime() - start);
        assertThat(took).as("the correlated receive wins the Listen; it does not wait for the delay branch").isLessThan(WINDOW);

        Exchange instance = completed().getExchanges().get(0);
        assertThat(claimNumber(instance)).isEqualTo(CLAIM);
        assertThat(instance.getProperty("msgClaim", String.class))
                .as("msgClaim is built from msgFnolCorrection").contains(CORRECTED_AMOUNT).contains("(corrected by agency)");

        Thread.sleep(WINDOW.plusSeconds(2).toMillis());
        assertThat(completed().getReceivedCounter()).as("the first FNOL must not run as an instance of its own").isEqualTo(1);
        assertThat(suspended().getReceivedCounter()).isZero();
        assertThat(LegacySystems.claims()).singleElement().satisfies(row -> {
            assertThat(row.claimNumber()).isEqualTo(CLAIM);
            assertThat(row.estimatedAmount()).isEqualByComparingTo(new BigDecimal(CORRECTED_AMOUNT));
        });
    }

    @Test
    @DisplayName("a second FNOL after the window starts a new instance, and the claims system rejects the duplicate")
    void fnolAfterWindowStartsNewInstance() throws Exception {
        send(original);
        awaitCompleted(1, WINDOW.plusSeconds(10));
        BigDecimal firstAmount = LegacySystems.claims().get(0).estimatedAmount();

        suspended().expectedMessageCount(1);
        send(correction);
        suspended().setResultWaitTime(WINDOW.plusSeconds(10).toMillis());
        suspended().assertIsSatisfied();

        Exchange second = suspended().getExchanges().get(0);
        assertThat(claimNumber(second)).isEqualTo(CLAIM);
        assertThat(second.getProperty("msgClaim", String.class)).as("the late FNOL ran as its own instance").contains(CORRECTED_AMOUNT);
        assertThat(second.getMessage().getHeader("FnolSuspendedReason", String.class))
                .as("usp_InsertClaim is refused on the claim number key").containsIgnoringCase("duplicate key");
        assertThat(completed().getReceivedCounter()).isEqualTo(1);
        assertThat(LegacySystems.claims()).singleElement().satisfies(row ->
                assertThat(row.estimatedAmount()).as("the first claim stays as inserted").isEqualByComparingTo(firstAmount));
    }

    @Test
    @DisplayName("FNOLs for different claim numbers do not correlate")
    void differentClaimsDoNotCorrelate() throws Exception {
        send(original);
        send(read(fixture("corpus/inputs/fnol/" + OTHER_CLAIM + ".xml")));
        awaitCompleted(2, WINDOW.plusSeconds(10));
        assertThat(completed().getExchanges()).extracting(FnolIntakeTestBase::claimNumber).containsExactlyInAnyOrder(CLAIM, OTHER_CLAIM);
    }

    @Test
    @DisplayName("the deployed correction window is the orchestration's 15 minutes")
    void productionWindowIsFifteenMinutes() throws Exception {
        try (InputStream in = Files.newInputStream(Path.of("src/main/resources/application.yaml"))) {
            Map<String, Object> yaml = new Yaml().load(in);
            Object window = path(yaml, "claimshub", "fnol", "correction-window");
            assertThat(window).as("claimshub.fnol.correction-window in application.yaml").isEqualTo("15m");
        }
    }

    private void awaitCompleted(int count, Duration within) throws InterruptedException {
        completed().expectedMinimumMessageCount(count);
        completed().setResultWaitTime(within.toMillis());
        completed().assertIsSatisfied();
    }

    @SuppressWarnings("unchecked")
    private static Object path(Map<String, Object> map, String... keys) {
        Object node = map;
        for (String key : keys) {
            if (!(node instanceof Map)) {
                return null;
            }
            node = ((Map<String, Object>) node).get(key);
        }
        return node;
    }
}
