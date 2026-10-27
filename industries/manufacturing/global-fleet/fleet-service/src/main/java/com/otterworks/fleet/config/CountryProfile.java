package com.otterworks.fleet.config;

import jakarta.validation.constraints.AssertTrue;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Positive;
import jakarta.validation.constraints.PositiveOrZero;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.Currency;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.validation.annotation.Validated;

@Validated
@ConfigurationProperties("fleet.country")
public record CountryProfile(
        @NotBlank String sourceApp,
        @NotNull Currency currency,
        @NotNull DistanceUnit distanceUnit,
        @PositiveOrZero int minGrade,
        @NotNull BenefitPercentSource benefitPercentSource,
        BigDecimal benefitPercent,
        @NotNull BigDecimal commutePercentPerUnit,
        @NotNull EmployeeContribution employeeContribution,
        @NotNull RoundingMode benefitRounding,
        @NotNull BigDecimal mileageRate,
        @NotNull RoundingMode mileageRounding,
        @Positive int claimLookbackMonths,
        @Positive int maxClaimDistance,
        @Positive int claimHistoryMonths,
        boolean payrollFile) {

    @AssertTrue(message = "benefitPercent is required when benefitPercentSource is PROFILE")
    public boolean isBenefitPercentPresentWhenRequired() {
        return benefitPercentSource != BenefitPercentSource.PROFILE || benefitPercent != null;
    }

    public enum DistanceUnit {
        MILE,
        KM
    }

    public enum BenefitPercentSource {
        VEHICLE,
        PROFILE
    }

    public enum EmployeeContribution {
        EMPLOYEE,
        NONE
    }
}
