package com.otterworks.insurance.claimshub.triage;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.Map;
import java.util.function.Function;
import java.util.stream.Collectors;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.springframework.core.io.ClassPathResource;

class RulesTableMatchesBreExportTest {

    private static RulesTable table;
    private static BrePolicyExport bre;

    @BeforeAll
    static void load() throws Exception {
        table = RulesTable.load(new ClassPathResource(Fixture.TABLE));
        bre = BrePolicyExport.load(Fixture.POLICY);
    }

    @Test
    void rulesTableAndBreExportNameTheSameRules() {
        assertThat(RuleNameGuard.differences(table.names(), bre.names()))
                .as("rules table %s against %s", Fixture.TABLE, Fixture.POLICY)
                .isEmpty();
        assertThat(table.names()).hasSize(bre.names().size());
    }

    @Test
    void eachRuleKeepsItsPriorityOutcomeAndReason() {
        Map<String, TriageRule> byName = table.rules().stream()
                .collect(Collectors.toMap(TriageRule::name, Function.identity()));
        for (BrePolicyExport.Rule rule : bre.rules()) {
            TriageRule row = byName.get(rule.name());
            assertThat(row).as(rule.name()).isNotNull();
            assertThat(row.priority()).as(rule.name() + " priority").isEqualTo(rule.priority());
            assertThat(row.outcome()).as(rule.name() + " outcome").isEqualTo(rule.outcome());
            assertThat(row.reason()).as(rule.name() + " reason").isEqualTo(rule.reason());
        }
    }

    @Test
    void guardReportsARenamedOrMissingRule() {
        var renamed = bre.names().stream().map(n -> n.equals("LargeLoss") ? "LargeLossUnit" : n).toList();
        assertThat(RuleNameGuard.differences(renamed, bre.names())).containsExactly(
                "in the rules table but not the BRE export: LargeLossUnit",
                "in the BRE export but not the rules table: LargeLoss");

        var dropped = bre.names().stream().filter(n -> !n.equals("FastTrack")).toList();
        assertThat(RuleNameGuard.differences(dropped, bre.names()))
                .containsExactly("in the BRE export but not the rules table: FastTrack");
    }
}
