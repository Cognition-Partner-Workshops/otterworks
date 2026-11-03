package com.otterworks.ottershops.pricing;

import java.math.BigDecimal;
import java.util.List;

public record Totals(
        int subtotalCents,
        int discountCents,
        int shippingCents,
        List<Fee> fees,
        int feesCents,
        BigDecimal taxRate,
        int taxCents,
        int totalCents) {}
