package com.otterworks.commission.calculation;

import static org.assertj.core.api.Assertions.assertThat;

import java.math.BigDecimal;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

class CommissionCalculatorTest {

    private static BigDecimal calc(String premium, String rate, String split) {
        return CommissionCalculator.commission(new BigDecimal(premium), new BigDecimal(rate), new BigDecimal(split));
    }

    @Test
    @DisplayName("R30 a half cent rounds up per row (Oracle ROUND, not HALF_EVEN)")
    void halfCentRoundsUp() {
        assertThat(calc("1200.00", "8.77", "50")).isEqualTo(new BigDecimal("4.39"));
    }

    @Test
    @DisplayName("R30 R37 a non-terminating premium/12 keeps Oracle NUMBER precision")
    void nonTerminatingDivision() {
        assertThat(calc("1000.00", "8", "50")).isEqualTo(new BigDecimal("3.33"));
        assertThat(calc("1000.00", "10", "33.34")).isEqualTo(new BigDecimal("2.78"));
        assertThat(calc("1000.00", "10", "33.33")).isEqualTo(new BigDecimal("2.78"));
    }

    @Test
    @DisplayName("R31 rows are rounded independently; the residue cent is not redistributed")
    void noRemainderRedistribution() {
        BigDecimal rows = calc("1000.00", "8", "50").add(calc("1000.00", "8", "50"));
        assertThat(rows).isEqualTo(new BigDecimal("6.66"));
    }

    @Test
    @DisplayName("R37 money is scale 2 BigDecimal")
    void scaleTwo() {
        assertThat(calc("9600.00", "9.5", "50").scale()).isEqualTo(2);
        assertThat(calc("9600.00", "9.5", "50")).isEqualTo(new BigDecimal("38.00"));
    }
}
