package example.claimshub.fnol;

import java.util.List;

/** What the ClaimTriage policy writes into the facts: the outcome and one reason per fired rule. */
public record TriageResult(String outcome, List<String> reasons) {
}
