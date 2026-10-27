package com.otterworks.fleet.benefit;

import java.math.BigDecimal;
import java.time.LocalDate;

public record BenefitPeriodView(
        String period,
        LocalDate startDate,
        LocalDate endDate,
        String status,
        BigDecimal mileageRate,
        Integer recordCount,
        BigDecimal totalTaxable,
        BigDecimal totalMileage) {
}
