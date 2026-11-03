package com.otterworks.ottershops.order;

import org.junit.jupiter.api.Test;

import java.math.BigDecimal;

import static org.junit.jupiter.api.Assertions.assertEquals;

class ReturnServiceTest {
    static OrderView.Line line(int qty, int total) {
        return new OrderView.Line(1, "SKU", "P1", "Tee", "Navy", "M", null, qty, 2000, total / qty, 0, total);
    }

    @Test
    void refundIsPaidPricePlusTax() {
        assertEquals(1085, ReturnService.refund(line(1, 1000), 1, new BigDecimal("8.50")));
    }

    @Test
    void partialQuantityIsProrated() {
        assertEquals(1999, ReturnService.refund(line(3, 5997), 1, BigDecimal.ZERO));
        assertEquals(4338, ReturnService.refund(line(3, 5997), 2, new BigDecimal("8.50")));
    }

    @Test
    void reasonListIsFixed() {
        assertEquals(6, ReturnService.REASONS.size());
    }
}
