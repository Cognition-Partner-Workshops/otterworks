package com.otterworks.fleet.eligibility;

import java.util.Locale;

public final class EmployeeNumbers {

    private EmployeeNumbers() {
    }

    public static String normalize(String employeeNo) {
        if (employeeNo == null || employeeNo.isBlank()) {
            return null;
        }
        return employeeNo.trim().toUpperCase(Locale.ROOT);
    }
}
