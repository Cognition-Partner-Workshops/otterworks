package com.otterworks.commission.calculation;

import java.math.BigDecimal;
import java.math.MathContext;
import java.math.RoundingMode;

import com.otterworks.commission.common.Money;

/**
 * ROUND(annual_premium / 12 * rate_pct / 100 * split_pct / 100, 2), evaluated
 * left to right as Oracle NUMBER does: a non-terminating quotient is cut to
 * Oracle's 40 significant digits at the step that divides.
 */
public final class CommissionCalculator {

    static final MathContext ORACLE_NUMBER = new MathContext(40, RoundingMode.HALF_UP);
    private static final BigDecimal TWELVE = BigDecimal.valueOf(12);
    private static final BigDecimal HUNDRED = BigDecimal.valueOf(100);

    private CommissionCalculator() {
    }

    public static BigDecimal commission(BigDecimal annualPremium, BigDecimal ratePct, BigDecimal splitPct) {
        BigDecimal v = annualPremium.divide(TWELVE, ORACLE_NUMBER);
        v = v.multiply(ratePct, ORACLE_NUMBER);
        v = v.divide(HUNDRED, ORACLE_NUMBER);
        v = v.multiply(splitPct, ORACLE_NUMBER);
        v = v.divide(HUNDRED, ORACLE_NUMBER);
        return Money.cents(v, Money.ORACLE_ROUND);
    }
}
