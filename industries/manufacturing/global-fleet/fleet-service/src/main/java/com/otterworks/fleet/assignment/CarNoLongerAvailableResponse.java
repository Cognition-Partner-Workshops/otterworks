package com.otterworks.fleet.assignment;

import java.util.List;

public record CarNoLongerAvailableResponse(
        String code,
        String message,
        List<PoolVehicle> pool) {
}
