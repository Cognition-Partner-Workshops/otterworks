package com.otterworks.fleet.assignment;

import java.math.BigDecimal;

public record NewVehicleInput(
        String plate,
        String make,
        String model,
        BigDecimal listPrice,
        Integer co2,
        String fuel,
        BigDecimal benefitPercent) {
}
