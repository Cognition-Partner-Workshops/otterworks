package com.otterworks.fleet.assignment;

import java.time.LocalDate;

public record CarRequestResult(
        Long requestId,
        Long assignmentId,
        String employeeNo,
        String registration,
        String reason,
        LocalDate startDate,
        String status) {
}
