package com.otterworks.fleet.returns;

import java.math.BigDecimal;
import java.time.LocalDate;

/**
 * Identify the car by {@code plate} or {@code vehicleId} (exactly one). {@code assignmentId},
 * when sent, must still be the car's open assignment. A missing {@code returnDate} means today.
 */
public record ReturnRequest(
        String plate,
        Long vehicleId,
        Long assignmentId,
        LocalDate returnDate,
        BigDecimal odometer,
        String conditionNote) {
}
