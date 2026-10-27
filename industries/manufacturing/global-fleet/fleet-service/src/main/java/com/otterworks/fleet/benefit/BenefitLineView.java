package com.otterworks.fleet.benefit;

import java.math.BigDecimal;
import java.time.LocalDate;

public record BenefitLineView(
        String registration,
        LocalDate from,
        LocalDate to,
        int days,
        BigDecimal monthlyBenefit,
        BigDecimal benefit) {
}
