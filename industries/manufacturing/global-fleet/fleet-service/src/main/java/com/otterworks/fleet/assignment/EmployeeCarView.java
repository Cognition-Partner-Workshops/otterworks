package com.otterworks.fleet.assignment;

import java.util.List;

public record EmployeeCarView(
        String employeeNo,
        AssignmentView current,
        List<AssignmentView> history) {
}
