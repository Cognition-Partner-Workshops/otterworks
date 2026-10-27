package com.otterworks.fleet.assignment;

import com.otterworks.fleet.eligibility.CarRequestStep;
import com.otterworks.fleet.eligibility.EligibilityDecision;
import java.time.LocalDate;
import java.util.List;
import java.util.UUID;

public record DraftView(
        UUID draftId,
        String employeeNo,
        CarRequestStep step,
        String vehicleChoice,
        Long poolVehicleId,
        NewVehicleInput newVehicle,
        String reason,
        LocalDate startDate,
        EligibilityDecision eligibility,
        Boolean vehicleAvailable,
        List<PoolVehicle> pool) {
}
