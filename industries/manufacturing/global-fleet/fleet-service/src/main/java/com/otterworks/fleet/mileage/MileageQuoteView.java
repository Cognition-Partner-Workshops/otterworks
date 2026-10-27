package com.otterworks.fleet.mileage;

import java.math.BigDecimal;

public record MileageQuoteView(
        Integer distance,
        String distanceUnit,
        BigDecimal rate,
        BigDecimal amount,
        String currency) {
}
