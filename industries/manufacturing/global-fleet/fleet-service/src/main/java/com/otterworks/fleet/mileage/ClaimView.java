package com.otterworks.fleet.mileage;

import com.otterworks.fleet.domain.MileageClaim;
import java.math.BigDecimal;
import java.time.Instant;
import java.time.LocalDate;

public record ClaimView(
        Long id,
        String employeeNo,
        Long employmentId,
        LocalDate journeyDate,
        Integer distance,
        String distanceUnit,
        BigDecimal rate,
        BigDecimal amount,
        String currency,
        String status,
        String paidPeriod,
        String vehicleRegistration,
        String purpose,
        Instant submittedAt,
        Instant decidedAt) {

    public static ClaimView from(MileageClaim claim, String distanceUnit, String currency) {
        return new ClaimView(
                claim.getId(),
                claim.getEmployment().getPerson().getEmployeeNo(),
                claim.getEmployment().getId(),
                claim.getClaimDate(),
                claim.getDistance(),
                distanceUnit,
                claim.getRate(),
                claim.getAmount(),
                currency,
                claim.getStatus().name(),
                claim.getPaidPeriod(),
                claim.getVehicle() == null ? null : claim.getVehicle().getRegistration(),
                claim.getPurpose(),
                claim.getSubmittedAt(),
                claim.getDecidedAt());
    }
}
