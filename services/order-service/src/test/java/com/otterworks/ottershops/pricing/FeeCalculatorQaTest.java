package com.otterworks.ottershops.pricing;

import org.junit.jupiter.api.Test;

import java.math.BigDecimal;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/** QA gap coverage: fees only where the law applies them, tax base, rewards-relevant totals. */
class FeeCalculatorQaTest {
    final FeeCalculator f = new FeeCalculator();

    @Test
    void coloradoFeeIsShipOnlyAndBagFeeIsCaliforniaPickupOnly() {
        assertTrue(f.fees(Fulfillment.PICKUP, null, "CO").isEmpty());
        assertTrue(f.fees(Fulfillment.SHIP, "CA", null).isEmpty());
        assertEquals(29, f.fees(Fulfillment.SHIP, " co ", null).get(0).amountCents());
        assertEquals(10, f.fees(Fulfillment.PICKUP, "AZ", "ca").get(0).amountCents());
    }

    @Test
    void expressIsAlwaysChargedAndPickupShipsFree() {
        assertEquals(1999, f.shipping(Fulfillment.SHIP, ShippingMethod.EXPRESS, 100_000));
        assertEquals(0, f.shipping(Fulfillment.PICKUP, ShippingMethod.EXPRESS, 100));
        assertEquals(799, f.shipping(Fulfillment.SHIP, ShippingMethod.STANDARD, 4999));
    }

    @Test
    void taxAppliesToShippingButNotToFees() {
        Totals t = f.totals(4000, 0, Fulfillment.SHIP, ShippingMethod.STANDARD, "CO", null);
        assertEquals(799, t.shippingCents());
        assertEquals(29, t.feesCents());
        assertEquals(139, t.taxCents()); // 2.90% of 47.99
        assertEquals(4000 + 799 + 29 + 139, t.totalCents());
    }

    @Test
    void californiaPickupTotalsIncludeBagFeeAndStoreTax() {
        Totals t = f.totals(2000, 300, Fulfillment.PICKUP, null, null, "CA");
        assertEquals(0, t.shippingCents());
        assertEquals(10, t.feesCents());
        assertEquals(123, t.taxCents()); // 7.25% of 17.00
        assertEquals(1700 + 10 + 123, t.totalCents());
    }

    @Test
    void unknownAndMissingStatesFallBackToDefaultRate() {
        assertEquals(FeeCalculator.DEFAULT_TAX_RATE, f.taxRate(null));
        assertEquals(FeeCalculator.DEFAULT_TAX_RATE, f.taxRate("ZZ"));
        assertEquals(new BigDecimal("0.00"), f.taxRate("or"));
    }
}
