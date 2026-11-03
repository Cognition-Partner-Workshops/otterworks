package com.otterworks.ottershops.common;

import java.math.BigDecimal;
import java.math.RoundingMode;

public final class Money {
    private Money() {}

    /** Applies a percentage to integer cents, rounding half up. */
    public static int percentOf(long cents, BigDecimal percent) {
        return BigDecimal.valueOf(cents).multiply(percent)
                .divide(BigDecimal.valueOf(100), 0, RoundingMode.HALF_UP).intValueExact();
    }

    public static int percentOf(long cents, int percent) {
        return percentOf(cents, BigDecimal.valueOf(percent));
    }

    public static String format(long cents) {
        return String.format("$%d.%02d", cents / 100, Math.abs(cents % 100));
    }
}
