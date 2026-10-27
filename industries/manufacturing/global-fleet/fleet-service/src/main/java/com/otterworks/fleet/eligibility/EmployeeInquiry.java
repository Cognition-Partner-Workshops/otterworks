package com.otterworks.fleet.eligibility;

import java.util.List;

public record EmployeeInquiry(
        String employeeNo,
        String lastName,
        String firstName,
        String currentCar,
        EmploymentView current,
        List<EmploymentView> employments,
        EligibilityDecision carRequest) {
}
