package com.otterworks.commission.common;

import static org.assertj.core.api.Assertions.assertThat;

import java.math.BigDecimal;

import org.junit.jupiter.api.Test;

class MoneyTest {

    @Test
    void oracleRoundIsHalfAwayFromZero() {
        assertThat(Money.cents(new BigDecimal("4.385"), Money.ORACLE_ROUND)).isEqualTo(new BigDecimal("4.39"));
        assertThat(Money.cents(new BigDecimal("-4.385"), Money.ORACLE_ROUND)).isEqualTo(new BigDecimal("-4.39"));
        assertThat(Money.cents(new BigDecimal("4.384999"), Money.ORACLE_ROUND)).isEqualTo(new BigDecimal("4.38"));
    }
}
