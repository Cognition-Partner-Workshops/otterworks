package com.otterworks.fleet.assignment;

import java.time.LocalDate;

public record ConfirmationRequest(String assignmentLegacyRef, LocalDate returnDate) {
}
