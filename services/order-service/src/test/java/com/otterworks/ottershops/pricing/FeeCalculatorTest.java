package com.otterworks.ottershops.pricing;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class FeeCalculatorTest {
    final FeeCalculator fees = new FeeCalculator();

    @Test
    void standardShippingFreeAtThresholdAfterDiscount() {
        assertEquals(799, fees.shipping(Fulfillment.SHIP, ShippingMethod.STANDARD, 4999));
        assertEquals(0, fees.shipping(Fulfillment.SHIP, ShippingMethod.STANDARD, 5000));
        assertEquals(1999, fees.shipping(Fulfillment.SHIP, ShippingMethod.EXPRESS, 9000));
        assertEquals(0, fees.shipping(Fulfillment.PICKUP, ShippingMethod.EXPRESS, 100));
    }

    @Test
    void coloradoDeliveryFeeAndCaliforniaPickupBagFee() {
        assertTrue(fees.fees(Fulfillment.SHIP, "CO", null).stream().anyMatch(f -> f.amountCents() == 29));
        assertTrue(fees.fees(Fulfillment.PICKUP, null, "CA").stream().anyMatch(f -> f.amountCents() == 10));
        assertTrue(fees.fees(Fulfillment.SHIP, "CA", null).isEmpty());
    }

    @Test
    void totalsAddUpInCents() {
        Totals t = fees.totals(4000, 600, Fulfillment.SHIP, ShippingMethod.STANDARD, "CO", null);
        assertEquals(t.subtotalCents() - t.discountCents() + t.shippingCents() + t.feesCents() + t.taxCents(), t.totalCents());
        assertEquals(799, t.shippingCents());
    }

    @Test
    void pickupTaxUsesStoreState() {
        Totals ca = fees.totals(10000, 0, Fulfillment.PICKUP, null, "OR", "CA");
        assertEquals(fees.taxRate("CA"), ca.taxRate());
    }
}
