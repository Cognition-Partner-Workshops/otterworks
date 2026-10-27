package com.otterworks.fleet.eligibility;

public record EmployeeSummary(
        String employeeNo,
        String lastName,
        String firstName,
        Integer grade,
        String status,
        String currentCar) {
}
