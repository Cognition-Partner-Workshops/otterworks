package com.otterworks.fleet.assignment;

import java.time.LocalDate;

public record AssignmentView(
        Long id,
        String legacyRef,
        String registration,
        String make,
        String model,
        LocalDate startDate,
        LocalDate endDate,
        String reason) {
}
