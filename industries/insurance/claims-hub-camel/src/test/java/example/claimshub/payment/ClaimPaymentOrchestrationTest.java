package example.claimshub.payment;

import static org.assertj.core.api.Assertions.assertThat;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.List;
import java.util.Map;

import org.apache.camel.Exchange;
import org.junit.jupiter.api.Test;

/**
 * Characterization of Orchestrations/ClaimPayment.odx with the vendor up, written from the XLANG/s:
 * {@code LedgerTx} (send Ledger.PostPayment) completes before {@code Vendor.DeliverRemittance} is sent; the
 * delivery loop makes at most three attempts; the send pipeline's trailer guard runs before the file leaves.
 */
class ClaimPaymentOrchestrationTest extends ReachableVendorTestSupport {

    @Test
    void theLedgerPostIsCommittedBeforeTheVendorFileGoesOut() throws Exception {
        Exchange result = pay("PI-2026-880100");

        assertThat(result.getException()).isNull();
        List<Send> sftp = recorder.sftpSends();
        assertThat(sftp).hasSize(1);
        assertThat(sftp.get(0).ledgerAtSend()).containsExactly("PI-2026-880100:POST");
        assertThat(vendorFilesFor("PI-2026-880100")).hasSize(1);
    }

    @Test
    void theLedgerIsPostedWithTheLedgerPostMapOutput() throws Exception {
        pay("PI-2026-880100");

        List<Map<String, Object>> entries = ledgerEntries("PI-2026-880100");
        assertThat(entries).hasSize(1);
        assertThat(entries.get(0).get("entry_type")).isEqualTo("POST");
        assertThat(entries.get(0).get("document")).isEqualTo(Files.readString(ledgerPostGolden("PI-2026-880100"), StandardCharsets.UTF_8));
        assertThat(entries.get(0).get("net_amount").toString()).isEqualTo("8613.64");
        assertThat(entries.get(0).get("line_count")).isEqualTo(3);
    }

    @Test
    void theVendorFileIsNamedByTheSendPortMacroAndWrittenThroughTheTemporaryFolder() throws Exception {
        pay("PI-2026-880100");

        assertThat(vendorFiles()).singleElement().asString().matches("REM_\\d{17}_PI-2026-880100\\.xml\\.txt");
        assertThat(vendorTempFiles()).isEmpty();
    }

    @Test
    void aVendorThatRecoversOnTheThirdAttemptGetsOneFileAndTheLedgerKeepsItsPost() throws Exception {
        setVendorInboxWritable(false);
        recorder.beforeSftpSend = attempt -> setVendorInboxWritable(attempt >= 3);

        Exchange result = pay("PI-2026-880104");

        assertThat(result.getException()).isNull();
        List<Send> sftp = recorder.sftpSends();
        assertThat(sftp).hasSize(3);
        for (int i = 1; i < sftp.size(); i++) {
            assertThat((sftp.get(i).nanos() - sftp.get(i - 1).nanos()) / 1_000_000).as("delay before attempt %d", i + 1)
                    .isGreaterThanOrEqualTo(TEST_RETRY_DELAY_MS);
        }
        assertThat(vendorFilesFor("PI-2026-880104")).hasSize(1);
        assertThat(ledgerEntries("PI-2026-880104")).extracting(e -> e.get("entry_type")).containsExactly("POST");
        assertThat(recorder.smtpSends()).isEmpty();
        assertThat(OPS_SMTP.getReceivedMessages()).isEmpty();
    }

    @Test
    void aLedgerPostThatFailsSendsNoFileAndNoReversal() throws Exception {
        jdbc.execute("create or replace function ledger.test_reject_post() returns trigger language plpgsql as "
                + "$$ begin raise exception 'ledger unavailable'; end $$");
        jdbc.execute("create trigger test_reject_post before insert on ledger.claim_payment_entry for each row "
                + "when (new.instruction_id = 'PI-2026-880101') execute function ledger.test_reject_post()");
        try {
            Exchange result = pay("PI-2026-880101");

            assertThat(result.getException()).isNotNull();
            assertThat(recorder.sftpSends()).isEmpty();
            assertThat(vendorFilesFor("PI-2026-880101")).isEmpty();
            assertThat(ledgerEntries("PI-2026-880101")).isEmpty();
            assertThat(OPS_SMTP.getReceivedMessages()).isEmpty();
        } finally {
            jdbc.execute("drop trigger if exists test_reject_post on ledger.claim_payment_entry");
            jdbc.execute("drop function if exists ledger.test_reject_post()");
        }
    }

    @Test
    void theTrailerGuardRefusesAFileWhoseTrailerDisagreesBeforeAnythingIsSent() throws Exception {
        String golden = Files.readString(remittanceGolden("PI-2026-880100"), StandardCharsets.US_ASCII);
        String tampered = golden.replace("TRL00000300000000966027", "TRL00000300000000966028");
        assertThat(TrailerTotalsReference.check(tampered)).isEqualTo("DebitTotalCents");

        Exchange result = producer.request("direct:vendor.deliver", exchange -> {
            exchange.getIn().setBody(tampered);
            exchange.getIn().setHeader(Exchange.FILE_NAME, "PI-2026-880100.xml");
        });

        assertThat(result.getException()).isNotNull();
        assertThat(result.getException()).hasStackTraceContaining("TrailerTotals").hasStackTraceContaining("DebitTotalCents");
        assertThat(recorder.sftpSends()).isEmpty();
        assertThat(vendorFiles()).isEmpty();
    }
}
