package com.otterworks.commission.screens;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.math.BigDecimal;
import java.util.List;

import org.junit.jupiter.api.Test;

class AmountsTest {

    @Test
    void formatsStoredScaleWithoutRounding() {
        assertThat(Amounts.format(new BigDecimal("8.5"))).isEqualTo("8.50");
        assertThat(Amounts.format(new BigDecimal("1418.50"))).isEqualTo("1,418.50");
        assertThatThrownBy(() -> Amounts.format(new BigDecimal("0.005"))).isInstanceOf(ArithmeticException.class);
    }

    @Test
    void totalIsExactSumOfRows() {
        ScreensRepository.StatementRow a = row("0.01");
        ScreensRepository.StatementRow b = row("50.01");
        assertThat(Amounts.total(List.of(a, b))).isEqualByComparingTo("50.02");
        assertThat(Amounts.total(List.of())).isEqualTo(new BigDecimal("0.00"));
    }

    private static ScreensRepository.StatementRow row(String amount) {
        return new ScreensRepository.StatementRow(1, 1, "P", "X", BigDecimal.ONE, 1, BigDecimal.ONE, BigDecimal.ONE,
                new BigDecimal(amount), null, null);
    }
}
