package com.otterworks.fleet.benefit;

import java.math.BigDecimal;
import java.util.List;

public record BenefitInquiryView(
        String employeeNo,
        String period,
        String status,
        List<BenefitLineView> lines,
        int carDays,
        BigDecimal taxableBenefit,
        int distance,
        BigDecimal mileageAmount,
        String leaverFlag,
        String currency) {
}
