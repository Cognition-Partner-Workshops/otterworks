package com.otterworks.insurance.claimshub.triage;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.springframework.core.io.ClassPathResource;

/** Thresholds, causes and order live in the table: editing the table changes the outcome. */
class RulesTableIsDataTest {

    private static String table() throws IOException {
        return new ClassPathResource(Fixture.TABLE).getContentAsString(StandardCharsets.UTF_8);
    }

    private static Map<String, String> facts(String claim) throws IOException {
        return TriageFactsReader.read(Files.readString(Fixture.FACTS.resolve(claim + ".xml")));
    }

    private static String outcome(String csv, String claim) throws IOException {
        return new TriageEvaluator(RulesTable.parse(csv)).evaluate(facts(claim)).outcome();
    }

    @Test
    void fastTrackLimitIsReadFromTheTable() throws IOException {
        // CLM-2026-100401 has NetExposure 1999.99; the v1.1 limit of 1500 would not fast-track it.
        assertThat(outcome(table(), "CLM-2026-100401")).isEqualTo("FAST_TRACK");
        assertThat(outcome(table().replace("NetExposure <= 2500.00", "NetExposure <= 1500.00"), "CLM-2026-100401"))
                .isEqualTo("STANDARD");
    }

    @Test
    void fastTrackCausesAreReadFromTheTable() throws IOException {
        assertThat(outcome(table(), "CLM-2026-100402")).isEqualTo("FAST_TRACK");
        assertThat(outcome(table().replace("(GLAS,TOWG,WIND)", "(GLAS,WIND)"), "CLM-2026-100402"))
                .isEqualTo("STANDARD");
    }

    @Test
    void largeLossAndFraudThresholdsAreReadFromTheTable() throws IOException {
        // CLM-2026-100409: reserve 48750.00, below the 50000.00 threshold.
        assertThat(outcome(table(), "CLM-2026-100409")).isEqualTo("STANDARD");
        assertThat(outcome(table().replace("ReserveEstimate >= 50000.00", "ReserveEstimate >= 48750.00"),
                "CLM-2026-100409")).isEqualTo("LARGE_LOSS");
        // CLM-2026-100405: reported 33 days after loss.
        assertThat(outcome(table().replace("ReportDelayDays > 30", "ReportDelayDays > 33"), "CLM-2026-100405"))
                .isEqualTo("STANDARD");
    }

    @Test
    void higherPriorityOutcomeWinsAndEveryFiredRuleAddsAReason() throws IOException {
        Map<String, String> facts = new java.util.HashMap<>(facts("CLM-2026-100405"));
        facts.put("InForceAtLoss", "false");
        facts.put("PriorFraudFlag", "true");
        TriageResult result = new TriageEvaluator(RulesTable.parse(table())).evaluate(facts);
        assertThat(result.outcome()).isEqualTo("DECLINE_NOT_IN_FORCE");
        assertThat(result.rulesFired())
                .containsExactly("DeclineNotInForce", "FraudFlagLateReport", "FraudFlagPriorHistory");
        assertThat(result.reasons()).containsExactly("Policy not in force at loss date",
                "Reported more than 30 days after loss", "Claimant has a prior fraud flag");
    }

    @Test
    void rulesRunInDescendingPriorityWhateverTheFileOrder() throws IOException {
        String[] lines = table().strip().split("\n");
        StringBuilder reversed = new StringBuilder(lines[0]).append('\n');
        for (int i = lines.length - 1; i > 0; i--) {
            reversed.append(lines[i]).append('\n');
        }
        assertThat(RulesTable.parse(reversed.toString()).rules().get(0).name()).isEqualTo("DeclineNotInForce");
        assertThat(RulesTable.parse(reversed.toString()).rules().get(6).name()).isEqualTo("StandardHandling");
    }

    @Test
    void malformedTablesAreRejected() {
        assertThatThrownBy(() -> RulesTable.parse("name,priority,condition,outcome,reason\n"))
                .hasMessageContaining("no rules");
        assertThatThrownBy(() -> RulesTable.parse("name,priority,condition,outcome,reason\n"
                + "A,1,Outcome == '',X,r\nA,2,Outcome == '',Y,r\n"))
                .hasMessageContaining("duplicate rule A");
        assertThatThrownBy(() -> RulesTable.parse("name,priority,condition,outcome,reason\n"
                + "A,1,Outcome ~ 1,X,r\n"))
                .hasMessageContaining("cannot parse");
    }
}
