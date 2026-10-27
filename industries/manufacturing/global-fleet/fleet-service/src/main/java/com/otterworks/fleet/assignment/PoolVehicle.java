package com.otterworks.fleet.assignment;

import java.math.BigDecimal;

public record PoolVehicle(
        Long id,
        String registration,
        String make,
        String model,
        BigDecimal listPrice,
        Integer co2,
        String fuel) {
}
