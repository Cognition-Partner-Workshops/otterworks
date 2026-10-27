package com.otterworks.fleet.mileage;

import com.otterworks.fleet.config.CountryProfile;
import java.math.BigDecimal;
import java.math.RoundingMode;
import org.springframework.stereotype.Component;

@Component
public class MileagePricing {

    private final CountryProfile profile;

    public MileagePricing(CountryProfile profile) {
        this.profile = profile;
    }

    public BigDecimal amount(int distance, BigDecimal rate) {
        return BigDecimal.valueOf(distance)
                .multiply(rate)
                .setScale(2, profile.mileageRounding());
    }

    public BigDecimal quote(int distance) {
        return amount(distance, profile.mileageRate());
    }
}
