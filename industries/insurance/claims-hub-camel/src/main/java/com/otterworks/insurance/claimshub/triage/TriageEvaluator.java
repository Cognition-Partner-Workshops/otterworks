package com.otterworks.insurance.claimshub.triage;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * Runs the rules table over one TriageFacts document with the BRE agenda the policy relies on:
 * rules in agenda order, each condition sees the Outcome set so far, the first outcome set wins,
 * and every rule that fires appends its reason.
 */
public final class TriageEvaluator {

    public static final String OUTCOME = "Outcome";

    private final RulesTable table;

    public TriageEvaluator(RulesTable table) {
        this.table = table;
    }

    public TriageResult evaluate(Map<String, String> facts) {
        Map<String, String> working = new HashMap<>(facts);
        working.put(OUTCOME, "");
        List<String> fired = new ArrayList<>();
        List<String> reasons = new ArrayList<>();
        for (TriageRule rule : table.rules()) {
            if (rule.condition().test(working)) {
                fired.add(rule.name());
                reasons.add(rule.reason());
                if (working.get(OUTCOME).isEmpty()) {
                    working.put(OUTCOME, rule.outcome());
                }
            }
        }
        return new TriageResult(facts.get("ClaimNumber"), working.get(OUTCOME), reasons, fired);
    }
}
