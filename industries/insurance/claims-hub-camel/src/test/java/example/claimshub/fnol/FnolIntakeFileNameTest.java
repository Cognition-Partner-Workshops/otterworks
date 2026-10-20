package example.claimshub.fnol;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.Duration;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import org.apache.camel.Exchange;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Import;
import org.springframework.context.annotation.Primary;

/**
 * The promoted ClaimNumber and AgencyId name the fraud referral, decline and glass fast-track files. An FNOL whose
 * ids are not one plain {@code CLM-nnnn-nnnnnn} / {@code AG-nnnn} is suspended before anything is written or
 * inserted. Triage here answers whatever claim number it is given (as the rules table does), so the file sinks
 * are reachable with a tampered id; the golden stub alone refuses most of them.
 */
@Import(FnolIntakeFileNameTest.AnyClaimNumberTriage.class)
@DisplayName("FnolIntake refuses claim numbers and agency ids that are not plain ids")
class FnolIntakeFileNameTest extends FnolIntakeTestBase {

    @TestConfiguration
    static class AnyClaimNumberTriage {
        private static final Pattern CORPUS_CLAIM = Pattern.compile("CLM-[0-9]{4}-[0-9]{6}");

        @Bean
        @Primary
        ClaimTriage anyClaimNumberTriage(GoldenTriageStub stub) {
            return (claimNumber, facts) -> {
                Matcher m = CORPUS_CLAIM.matcher(claimNumber == null ? "" : claimNumber);
                return stub.evaluate(m.find() ? m.group() : claimNumber, facts);
            };
        }
    }

    @BeforeEach
    void clean() throws Exception {
        reset();
    }

    @Test
    @DisplayName("sp_Fraud_Referral_FILE: a claim number with ../ does not overwrite another claim's referral")
    void fraudReferralClaimNumberWithParentSegment() throws Exception {
        sendWithClaimNumber("CLM-2026-100405", "CLM-2026-100405/../CLM-2026-100410");
        assertSuspendedWithNothingWritten("ClaimNumber");
    }

    @Test
    @DisplayName("sp_Fraud_Referral_FILE: a claim number with a sub-folder is refused")
    void fraudReferralClaimNumberWithSubFolder() throws Exception {
        sendWithClaimNumber("CLM-2026-100410", "CLM-2026-100410/extra");
        assertSuspendedWithNothingWritten("ClaimNumber");
    }

    @Test
    @DisplayName("sp_Declines_FILE: an agency id with ../ does not drop a decline in another agency's folder")
    void declineAgencyIdWithParentSegment() throws Exception {
        String fnol = read(fixture("corpus/inputs/fnol/CLM-2026-100403.xml"))
                .replace("<ProducerId>AG-0417</ProducerId>", "<ProducerId>AG-0417/../AG-0922</ProducerId>");
        assertThat(fnol).contains("AG-0417/../AG-0922");
        send(fnol);
        assertSuspendedWithNothingWritten("AgencyId");
    }

    @Test
    @DisplayName("sp_GlassVendor_FastTrack_SFTP: a claim number with a sub-folder is refused before usp_InsertClaim")
    void glassFastTrackClaimNumberWithSubFolder() throws Exception {
        sendWithClaimNumber("CLM-2026-100400", "CLM-2026-100400/x");
        assertSuspendedWithNothingWritten("ClaimNumber");
    }

    private void sendWithClaimNumber(String corpusClaim, String tampered) {
        String fnol = read(fixture("corpus/inputs/fnol/" + corpusClaim + ".xml"))
                .replace("<ClaimNumber>" + corpusClaim + "</ClaimNumber>", "<ClaimNumber>" + tampered + "</ClaimNumber>");
        assertThat(fnol).contains("<ClaimNumber>" + tampered + "</ClaimNumber>");
        send(fnol);
    }

    private void assertSuspendedWithNothingWritten(String header) throws Exception {
        long deadline = System.nanoTime() + WINDOW.plusSeconds(15).toNanos();
        while (completed().getReceivedCounter() + suspended().getReceivedCounter() == 0 && System.nanoTime() < deadline) {
            Thread.sleep(250);
        }
        Thread.sleep(Duration.ofMillis(500).toMillis());
        assertThat(outFiles("")).as("files written under the FILE/SFTP roots").isEmpty();
        assertThat(LegacySystems.claims()).as("claims inserted").isEmpty();
        assertThat(completed().getReceivedCounter()).as("completed instances").isZero();
        assertThat(suspended().getReceivedCounter()).as("suspended instances").isEqualTo(1);
        Exchange instance = suspended().getExchanges().get(0);
        assertThat(instance.getMessage().getHeader("FnolSuspendedReason", String.class)).contains(header);
    }
}
