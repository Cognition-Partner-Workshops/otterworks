package com.otterworks.fleet.returns;

import com.otterworks.fleet.config.CountryProfile.DistanceUnit;
import java.time.LocalDate;

public record ReturnCandidate(
        Long vehicleId,
        String registration,
        String make,
        String model,
        Long assignmentId,
        String employeeNo,
        String firstName,
        String lastName,
        LocalDate startDate,
        Integer lastOdometer,
        DistanceUnit distanceUnit) {
}
