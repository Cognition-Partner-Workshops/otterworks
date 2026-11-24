package example.claimshub.payment;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.List;
import java.util.Map;

import jakarta.mail.Message;
import jakarta.mail.internet.InternetAddress;
import jakarta.mail.internet.MimeMessage;

import org.apache.camel.Exchange;
import org.apache.camel.builder.AdviceWith;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.springframework.test.annotation.DirtiesContext;

import com.icegreen.greenmail.util.GreenMailUtil;

/**
 * A remittance the trailer guard refuses inside PaymentTx: nothing goes to the vendor, the ledger post is
 * reversed with the same msgLedgerPost, and operations is mailed with the guard's reason (decision 4 on the
 * ClaimPayment PR). The corpus maps never produce a disagreeing trailer, so the test corrupts the trailer's
 * DebitTotalCents by one cent as the file enters Vendor.DeliverRemittance.
 */
@DirtiesContext(classMode = DirtiesContext.ClassMode.AFTER_CLASS)
class ClaimPaymentTrailerRefusedTest extends ReachableVendorTestSupport {

    @BeforeAll
    void corruptTheTrailer() throws Exception {
        AdviceWith.adviceWith(camelContext, "vendor.DeliverRemittance", a -> a.weaveAddFirst().process(e -> {
            String file = e.getMessage().getBody(String.class);
            int trl = file.indexOf("\r\nTRL") + 2;
            long debit = Long.parseLong(file.substring(trl + 9, trl + 23)) + 1;
            e.getMessage().setBody(file.substring(0, trl + 9) + String.format("%014d", debit) + file.substring(trl + 23));
        }));
    }

    @Test
    void aRefusedFileIsNeverSentTheLedgerPostIsReversedAndOperationsIsMailed() throws Exception {
        Exchange result = pay("PI-2026-880100");

        assertThat(recorder.sftpSends()).isEmpty();
        assertThat(vendorFiles()).isEmpty();

        List<Map<String, Object>> entries = ledgerEntries("PI-2026-880100");
        assertThat(entries).extracting(e -> e.get("entry_type")).containsExactly("POST", "REVERSAL");
        assertThat(entries.get(1).get("document")).isEqualTo(entries.get(0).get("document"));

        List<Send> smtp = recorder.smtpSends();
        assertThat(smtp).hasSize(1);
        assertThat(smtp.get(0).ledgerAtSend()).containsExactly("PI-2026-880100:POST", "PI-2026-880100:REVERSAL");

        assertThat(OPS_SMTP.waitForIncomingEmail(5000, 1)).isTrue();
        MimeMessage[] mails = OPS_SMTP.getReceivedMessages();
        assertThat(mails).hasSize(1);
        assertThat(mails[0].getRecipients(Message.RecipientType.TO)).extracting(a -> ((InternetAddress) a).getAddress())
                .containsExactly(OPS_MAILBOX);
        assertThat(mails[0].getFrom()).extracting(a -> ((InternetAddress) a).getAddress()).containsExactly(HUB_SENDER);
        assertThat(mails[0].getSubject()).isEqualTo("Payment held: CLM-2026-100400");
        assertThat(GreenMailUtil.getBody(mails[0])).contains("PI-2026-880100").contains("trailer check")
                .contains("DebitTotalCents").contains("ledger post has been reversed");

        assertThat(result.getException()).as("the exception handler of PaymentTx handles the refusal").isNull();
    }
}
