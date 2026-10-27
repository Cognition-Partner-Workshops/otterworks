package com.otterworks.fleet.mileage;

import java.time.LocalDate;
import java.util.List;

public record MileageHistoryView(
        String employeeNo,
        LocalDate from,
        LocalDate to,
        List<ClaimView> claims) {
}
