package com.otterworks.fleet.eligibility;

import java.time.LocalDate;

public record BelowGradeHolder(
        String employeeNo,
        String lastName,
        String firstName,
        Integer grade,
        int minGrade,
        Long employmentId,
        Long assignmentId,
        String registration,
        LocalDate startDate,
        LocalDate endDate) {

    public BelowGradeHolder(
            String employeeNo,
            String lastName,
            String firstName,
            Integer grade,
            Integer minGrade,
            Long employmentId,
            Long assignmentId,
            String registration,
            LocalDate startDate,
            LocalDate endDate) {
        this(employeeNo, lastName, firstName, grade, minGrade.intValue(),
                employmentId, assignmentId, registration, startDate, endDate);
    }
}
