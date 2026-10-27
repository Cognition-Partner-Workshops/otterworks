package com.otterworks.fleet.eligibility;

import com.otterworks.fleet.domain.Employment;
import com.otterworks.fleet.domain.EmploymentStatus;
import java.time.LocalDate;

public record EmploymentView(
        Long id,
        Integer grade,
        EmploymentStatus status,
        LocalDate hireDate,
        LocalDate leaveDate) {

    public static EmploymentView from(Employment employment) {
        return new EmploymentView(
                employment.getId(),
                employment.getGrade(),
                employment.getStatus(),
                employment.getHireDate(),
                employment.getLeaveDate());
    }
}
