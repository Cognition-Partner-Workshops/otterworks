package com.otterworks.fleet.mileage;

import java.math.BigDecimal;
import java.time.LocalDate;

public record MileageClaimRequest(
        String employeeNo,
        LocalDate journeyDate,
        BigDecimal distance,
        String purpose) {
}
