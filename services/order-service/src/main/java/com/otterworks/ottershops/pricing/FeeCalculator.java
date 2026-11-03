package com.otterworks.ottershops.pricing;

import com.otterworks.ottershops.common.Money;
import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import org.springframework.stereotype.Component;

@Component
public class FeeCalculator {
    public static final int STANDARD_CENTS = 799;
    public static final int EXPRESS_CENTS = 1999;
    public static final int FREE_SHIPPING_THRESHOLD_CENTS = 5000;
    public static final BigDecimal DEFAULT_TAX_RATE = new BigDecimal("5.00");

    private static final Map<String, BigDecimal> TAX_RATES = Map.ofEntries(
            Map.entry("CA", new BigDecimal("7.25")),
            Map.entry("NY", new BigDecimal("4.00")),
            Map.entry("TX", new BigDecimal("6.25")),
            Map.entry("WA", new BigDecimal("6.50")),
            Map.entry("OR", new BigDecimal("0.00")),
            Map.entry("IL", new BigDecimal("6.25")),
            Map.entry("MA", new BigDecimal("6.25")),
            Map.entry("CO", new BigDecimal("2.90")),
            Map.entry("GA", new BigDecimal("4.00")),
            Map.entry("FL", new BigDecimal("6.00")),
            Map.entry("AZ", new BigDecimal("5.60")),
            Map.entry("MN", new BigDecimal("6.875")),
            Map.entry("NC", new BigDecimal("4.75")),
            Map.entry("PA", new BigDecimal("6.00")));

    public int shipping(Fulfillment fulfillment, ShippingMethod method, int merchandiseAfterDiscountCents) {
        if (fulfillment == Fulfillment.PICKUP) {
            return 0;
        }
        if (method == ShippingMethod.EXPRESS) {
            return EXPRESS_CENTS;
        }
        return merchandiseAfterDiscountCents >= FREE_SHIPPING_THRESHOLD_CENTS ? 0 : STANDARD_CENTS;
    }

    public BigDecimal taxRate(String state) {
        if (state == null) {
            return DEFAULT_TAX_RATE;
        }
        return TAX_RATES.getOrDefault(state.trim().toUpperCase(Locale.ROOT), DEFAULT_TAX_RATE);
    }

    public List<Fee> fees(Fulfillment fulfillment, String shipState, String storeState) {
        List<Fee> fees = new ArrayList<>();
        if (fulfillment == Fulfillment.SHIP && "CO".equalsIgnoreCase(trim(shipState))) {
            fees.add(new Fee("CO_RETAIL_DELIVERY", "Colorado retail delivery fee", 29));
        }
        if (fulfillment == Fulfillment.PICKUP && "CA".equalsIgnoreCase(trim(storeState))) {
            fees.add(new Fee("BAG_FEE", "California bag fee", 10));
        }
        return fees;
    }

    /**
     * @param shipState destination state for SHIP orders (may be null for a quote)
     * @param storeState the pickup store's state for PICKUP orders
     */
    public Totals totals(int subtotalCents, int discountCents, Fulfillment fulfillment, ShippingMethod method,
                         String shipState, String storeState) {
        int merchandise = subtotalCents - discountCents;
        int shipping = shipping(fulfillment, method == null ? ShippingMethod.STANDARD : method, merchandise);
        List<Fee> fees = fees(fulfillment, shipState, storeState);
        int feesCents = fees.stream().mapToInt(Fee::amountCents).sum();
        String taxState = fulfillment == Fulfillment.PICKUP ? storeState : shipState;
        BigDecimal rate = taxRate(taxState);
        int tax = Money.percentOf((long) merchandise + shipping, rate);
        return new Totals(subtotalCents, discountCents, shipping, fees, feesCents, rate, tax,
                merchandise + shipping + feesCents + tax);
    }

    private static String trim(String s) {
        return s == null ? null : s.trim();
    }
}
