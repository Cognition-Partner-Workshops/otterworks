package com.otterworks.commission.common;

import static org.assertj.core.api.Assertions.assertThat;

import java.math.BigDecimal;
import java.time.LocalDateTime;

import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.junit.jupiter.api.Test;

class OracleTextTest {

    @ParameterizedTest
    @CsvSource({"8.50,8.5", "0.5,.5", "-0.5,-.5", "0.01,.01", "50,50", "50.001,50.001", "100.00,100", "0.00,0",
            "-1,-1", "99.99,99.99", "1E+2,100"})
    void toCharMatchesOracleDefault(String in, String expected) {
        assertThat(OracleText.toChar(new BigDecimal(in))).isEqualTo(expected);
    }

    @Test
    void nullConcatenatesAsEmpty() {
        assertThat(OracleText.toChar((BigDecimal) null)).isEmpty();
        assertThat(OracleText.toChar((Long) null)).isEmpty();
    }

    @Test
    void wireDatesRoundTrip() {
        LocalDateTime d = OracleText.parseWireDate("2028-02-29 00:00:00");
        assertThat(OracleText.isoDay(d)).isEqualTo("2028-02-29");
        assertThat(OracleText.parseNumber(".5")).isEqualByComparingTo("0.5");
        assertThat(OracleText.parseNumber("-.5")).isEqualByComparingTo("-0.5");
    }
}
