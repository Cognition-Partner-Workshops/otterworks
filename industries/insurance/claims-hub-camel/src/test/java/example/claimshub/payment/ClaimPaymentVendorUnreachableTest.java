package example.claimshub.payment;

import static org.assertj.core.api.Assertions.assertThat;

import java.math.BigDecimal;
import java.util.List;
import java.util.Map;

import jakarta.mail.Message;
import jakarta.mail.internet.InternetAddress;
import jakarta.mail.internet.MimeMessage;

import org.apache.camel.Exchange;
import org.junit.jupiter.api.Test;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;

import com.icegreen.greenmail.util.GreenMailUtil;

/**
 * Characterization of the {@code VendorUnreachableException} path of ClaimPayment.odx: three attempts with
 * the retry delay after each failure, then {@code compensate LedgerTx} (Ledger.ReversePayment with the same
 * msgLedgerPost), then {@code OpsMail.Notify}. Nobody listens on the vendor port.
 */
class ClaimPaymentVendorUnreachableTest extends ClaimPaymentTestSupport {

    @DynamicPropertySource
    static void unreachableVendor(DynamicPropertyRegistry registry) {
        hubProperties(registry, false);
    }

    @Test
    void threeAttemptsThenTheLedgerPostIsReversedWithTheSameDocumentThenOperationsIsMailed() throws Exception {
        Exchange result = pay("PI-2026-880103");

        List<Send> sftp = recorder.sftpSends();
        assertThat(sftp).hasSize(3);
        assertThat(sftp).allSatisfy(s -> assertThat(s.ledgerAtSend()).containsExactly("PI-2026-880103:POST"));
        for (int i = 1; i < sftp.size(); i++) {
            assertThat((sftp.get(i).nanos() - sftp.get(i - 1).nanos()) / 1_000_000).as("delay before attempt %d", i + 1)
                    .isGreaterThanOrEqualTo(TEST_RETRY_DELAY_MS);
        }

        List<Map<String, Object>> entries = ledgerEntries("PI-2026-880103");
        assertThat(entries).extracting(e -> e.get("entry_type")).containsExactly("POST", "REVERSAL");
        Map<String, Object> post = entries.get(0);
        Map<String, Object> reversal = entries.get(1);
        assertThat(reversal.get("document")).isEqualTo(post.get("document"));
        assertThat(((BigDecimal) reversal.get("net_amount")).negate()).isEqualByComparingTo((BigDecimal) post.get("net_amount"));
        assertThat(((BigDecimal) post.get("net_amount"))).isEqualByComparingTo("9847.53");

        List<Send> smtp = recorder.smtpSends();
        assertThat(smtp).hasSize(1);
        assertThat(smtp.get(0).ledgerAtSend()).containsExactly("PI-2026-880103:POST", "PI-2026-880103:REVERSAL");
        assertThat(smtp.get(0).nanos()).isGreaterThan(sftp.get(2).nanos());

        assertThat(OPS_SMTP.waitForIncomingEmail(5000, 1)).isTrue();
        MimeMessage[] mails = OPS_SMTP.getReceivedMessages();
        assertThat(mails).hasSize(1);
        assertThat(mails[0].getRecipients(Message.RecipientType.TO)).extracting(a -> ((InternetAddress) a).getAddress())
                .containsExactly(OPS_MAILBOX);
        assertThat(mails[0].getFrom()).extracting(a -> ((InternetAddress) a).getAddress()).containsExactly(HUB_SENDER);
        assertThat(mails[0].getSubject()).isEqualTo("Payment held: CLM-2026-100409");
        assertThat(GreenMailUtil.getBody(mails[0])).contains("PI-2026-880103").contains("3 attempts");

        assertThat(vendorFiles()).isEmpty();
        assertThat(result.getException()).as("the exception handler of PaymentTx handles VendorUnreachableException").isNull();
    }
}
