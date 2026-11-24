package com.otterworks.insurance.claimshub.triage;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.Map;
import org.junit.jupiter.api.Test;

class ConditionTest {

    @Test
    void decimalsCompareByValueNotScale() {
        assertThat(Condition.parse("NetExposure <= 2500.00").test(Map.of("NetExposure", "2500"))).isTrue();
        assertThat(Condition.parse("NetExposure <= 2500.00").test(Map.of("NetExposure", "2500.01"))).isFalse();
        assertThat(Condition.parse("ReserveEstimate >= 50000.00").test(Map.of("ReserveEstimate", "50000.000")))
                .isTrue();
        assertThat(Condition.parse("ReportDelayDays > 30").test(Map.of("ReportDelayDays", "30"))).isFalse();
    }

    @Test
    void booleansStringsAndLists() {
        assertThat(Condition.parse("InjuryFlag == false").test(Map.of("InjuryFlag", "false"))).isTrue();
        assertThat(Condition.parse("InjuryFlag == false").test(Map.of("InjuryFlag", "true"))).isFalse();
        assertThat(Condition.parse("Outcome == ''").test(Map.of("Outcome", ""))).isTrue();
        assertThat(Condition.parse("Outcome != ''").test(Map.of("Outcome", "STANDARD"))).isTrue();
        assertThat(Condition.parse("LossCause in (GLAS, TOWG,WIND)").test(Map.of("LossCause", "TOWG"))).isTrue();
        assertThat(Condition.parse("LossCause in (GLAS,TOWG,WIND)").test(Map.of("LossCause", "glas"))).isFalse();
    }

    @Test
    void allClausesMustHold() {
        Condition c = Condition.parse("PolicyAgeDaysAtLoss < 90 and EstimatedAmount > 5000.00");
        assertThat(c.test(Map.of("PolicyAgeDaysAtLoss", "62", "EstimatedAmount", "5200.00"))).isTrue();
        assertThat(c.test(Map.of("PolicyAgeDaysAtLoss", "62", "EstimatedAmount", "5000.00"))).isFalse();
        assertThat(c.facts()).containsExactly("PolicyAgeDaysAtLoss", "EstimatedAmount");
    }

    @Test
    void rejectsWhatItCannotEvaluate() {
        assertThatThrownBy(() -> Condition.parse("InjuryFlag > false")).hasMessageContaining("needs a number");
        assertThatThrownBy(() -> Condition.parse("LossCause == GLAS")).hasMessageContaining("unknown literal");
        assertThatThrownBy(() -> Condition.parse(" ")).hasMessageContaining("empty");
        assertThatThrownBy(() -> Condition.parse("ReportDelayDays > 30").test(Map.of()))
                .hasMessageContaining("fact 'ReportDelayDays' is missing");
    }
}
