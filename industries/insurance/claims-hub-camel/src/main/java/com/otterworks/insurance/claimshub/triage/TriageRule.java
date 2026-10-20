package com.otterworks.insurance.claimshub.triage;

public record TriageRule(String name, int priority, Condition condition, String outcome, String reason) {
}
