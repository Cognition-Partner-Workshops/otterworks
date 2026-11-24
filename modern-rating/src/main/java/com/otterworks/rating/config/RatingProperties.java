package com.otterworks.rating.config;

import java.math.BigDecimal;
import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * @param tablesDir directory holding the shared flat-file rating tables
 * @param policyFee flat fee added to every quoted policy
 */
@ConfigurationProperties(prefix = "rating")
public record RatingProperties(String tablesDir, BigDecimal policyFee) {

    public RatingProperties {
        if (tablesDir == null || tablesDir.isBlank()) {
            tablesDir = "../legacy-rating/tables";
        }
        if (policyFee == null) {
            policyFee = new BigDecimal("35.00");
        }
    }
}
