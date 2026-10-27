package com.otterworks.fleet.mileage;

import java.math.BigDecimal;

public record MileageReimbursementView(
        String employeeNo,
        String period,
        int claimCount,
        long distance,
        BigDecimal amount,
        String currency) {
}
