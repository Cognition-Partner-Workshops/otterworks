package com.otterworks.fleet.assignment;

import java.time.Instant;
import java.time.LocalDate;

public record ConfirmationView(
        String employmentLegacyRef,
        String assignmentLegacyRef,
        LocalDate confirmedReturnDate,
        Instant confirmedAt) {
}
