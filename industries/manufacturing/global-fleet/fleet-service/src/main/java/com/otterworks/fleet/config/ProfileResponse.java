package com.otterworks.fleet.config;

import java.math.BigDecimal;

public record ProfileResponse(
        String sourceApp,
        String currency,
        String distanceUnit,
        int minGrade,
        String benefitPercentSource,
        String benefitPercent,
        String commutePercentPerUnit,
        String employeeContribution,
        String benefitRounding,
        String mileageRate,
        String mileageRounding,
        int claimLookbackMonths,
        int maxClaimDistance,
        int claimHistoryMonths,
        boolean payrollFile) {

    public static ProfileResponse from(CountryProfile profile) {
        return new ProfileResponse(
                profile.sourceApp(),
                profile.currency().getCurrencyCode(),
                profile.distanceUnit().name(),
                profile.minGrade(),
                profile.benefitPercentSource().name(),
                decimal(profile.benefitPercent()),
                decimal(profile.commutePercentPerUnit()),
                profile.employeeContribution().name(),
                profile.benefitRounding().name(),
                decimal(profile.mileageRate()),
                profile.mileageRounding().name(),
                profile.claimLookbackMonths(),
                profile.maxClaimDistance(),
                profile.claimHistoryMonths(),
                profile.payrollFile());
    }

    private static String decimal(BigDecimal value) {
        return value == null ? null : value.toString();
    }
}
