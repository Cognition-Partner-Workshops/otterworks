package com.halvergate.integration;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.HashMap;
import java.util.Map;

public final class FeeActivities {
    private static final Map<String, BigDecimal> RATES = new HashMap<>();

    private FeeActivities() {}

    public static String dailyFee(String balance, String rate, String accountType) {
        BigDecimal appliedRate = RATES.computeIfAbsent(accountType, key -> new BigDecimal(rate));
        return new BigDecimal(balance).multiply(appliedRate).setScale(2, RoundingMode.HALF_EVEN).toPlainString();
    }

    public static String roundHalfEven(String amount) {
        return new BigDecimal(amount).setScale(2, RoundingMode.HALF_EVEN).toPlainString();
    }
}
