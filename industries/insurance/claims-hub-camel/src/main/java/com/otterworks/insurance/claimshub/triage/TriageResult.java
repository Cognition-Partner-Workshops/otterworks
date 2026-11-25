package com.otterworks.insurance.claimshub.triage;

import java.util.List;

public record TriageResult(String claimNumber, String outcome, List<String> reasons, List<String> rulesFired) {
}
