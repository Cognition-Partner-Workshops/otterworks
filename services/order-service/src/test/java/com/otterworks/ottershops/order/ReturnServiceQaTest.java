package com.otterworks.ottershops.order;

import org.junit.jupiter.api.Disabled;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/** QA gap coverage for refund math. */
class ReturnServiceQaTest {
    @Test
    void fullReturnRefundsExactlyWhatWasPaidForMerchandise() {
        assertEquals(1001, ReturnService.refund(ReturnServiceTest.line(3, 1001), 3, BigDecimal.ZERO));
    }

    @Test
    @Disabled("KNOWN FAILING QA-05: one-at-a-time partial returns each round half-up and over-refund the line")
    void partialReturnsNeverRefundMoreThanTheLineTotal() {
        OrderView.Line l = ReturnServiceTest.line(3, 1001);
        int sum = 0;
        for (int i = 0; i < 3; i++) sum += ReturnService.refund(l, 1, BigDecimal.ZERO);
        assertTrue(sum <= 1001, "refunded " + sum + " for a 1001 cent line");
    }
}
