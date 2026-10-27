package com.otterworks.fleet.returns;

import com.otterworks.fleet.config.CountryProfile.DistanceUnit;
import java.time.LocalDate;

public record ReturnView(
        Long returnId,
        Long assignmentId,
        Long vehicleId,
        String registration,
        String employeeNo,
        LocalDate startDate,
        LocalDate returnDate,
        Integer odometer,
        DistanceUnit distanceUnit,
        String conditionNote) {
}
