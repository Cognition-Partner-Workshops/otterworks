package com.otterworks.fleet.assignment;

import java.time.LocalDate;

public record DoubleHolderAssignmentView(
        String legacyRef,
        String vehicleId,
        LocalDate startDate,
        String reason) {
}
