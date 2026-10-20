package com.otterworks.commission.common;

import java.math.BigDecimal;
import java.math.RoundingMode;

/**
 * Money is BigDecimal at scale 2 and every call site names its rounding mode.
 * Oracle ROUND(x, 2) on NUMBER rounds half away from zero, which is HALF_UP.
 */
public final class Money {

    public static final int SCALE = 2;
    public static final RoundingMode ORACLE_ROUND = RoundingMode.HALF_UP;

    private Money() {
    }

    public static BigDecimal cents(BigDecimal amount, RoundingMode mode) {
        return amount.setScale(SCALE, mode);
    }
}
