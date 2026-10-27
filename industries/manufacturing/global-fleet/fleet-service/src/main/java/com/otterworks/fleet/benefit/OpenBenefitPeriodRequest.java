package com.otterworks.fleet.benefit;

import jakarta.validation.constraints.NotBlank;

public record OpenBenefitPeriodRequest(@NotBlank String period) {
}
