package example.claimshub.payment;

import java.time.Duration;

import org.apache.camel.Exchange;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

/**
 * XLANG/s runs {@code compensate LedgerTx} to completion before the next shape. Camel's in-memory saga
 * coordinator starts the compensation asynchronously and does not wait for it, so the ops mail waits here
 * until Ledger.ReversePayment has recorded the reversal, and fails the exchange instead of mailing if it never does.
 */
@Component
public class LedgerReversals {

    private final JdbcTemplate jdbc;
    private final Duration timeout;

    public LedgerReversals(JdbcTemplate jdbc, @Value("${claims.payment.ledger.reversal-timeout}") Duration timeout) {
        this.jdbc = jdbc;
        this.timeout = timeout;
    }

    public void awaitReversal(Exchange exchange) throws Exception {
        String instructionId = OpsMail.instructionId(exchange.getProperty(ClaimPaymentRoutes.INSTRUCTION, String.class));
        long deadline = System.nanoTime() + timeout.toNanos();
        while (!reversed(instructionId)) {
            if (System.nanoTime() > deadline) {
                throw new IllegalStateException("Ledger.ReversePayment for " + instructionId + " not recorded within " + timeout);
            }
            Thread.sleep(50);
        }
    }

    private boolean reversed(String instructionId) {
        Integer n = jdbc.queryForObject("select count(*) from ledger.claim_payment_entry where instruction_id = ? and entry_type = 'REVERSAL'",
                Integer.class, instructionId);
        return n != null && n > 0;
    }
}
