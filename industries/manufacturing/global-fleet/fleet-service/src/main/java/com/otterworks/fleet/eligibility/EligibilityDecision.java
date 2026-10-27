package com.otterworks.fleet.eligibility;

public record EligibilityDecision(
        boolean allowed,
        EligibilityReason reason,
        String employeeNo,
        Long employmentId) {

    public static EligibilityDecision allow(String employeeNo, Long employmentId) {
        return new EligibilityDecision(true, null, employeeNo, employmentId);
    }

    public static EligibilityDecision refuse(EligibilityReason reason, String employeeNo) {
        return refuse(reason, employeeNo, null);
    }

    public static EligibilityDecision refuse(
            EligibilityReason reason, String employeeNo, Long employmentId) {
        return new EligibilityDecision(false, reason, employeeNo, employmentId);
    }
}
