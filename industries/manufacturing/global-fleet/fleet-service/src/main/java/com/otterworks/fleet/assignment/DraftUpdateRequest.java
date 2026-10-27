package com.otterworks.fleet.assignment;

import com.otterworks.fleet.eligibility.CarRequestStep;
import java.time.LocalDate;

public record DraftUpdateRequest(
        CarRequestStep step,
        String vehicleChoice,
        Long poolVehicleId,
        NewVehicleInput newVehicle,
        String reason,
        LocalDate startDate) {
}
