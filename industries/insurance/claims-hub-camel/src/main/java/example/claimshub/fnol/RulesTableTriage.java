package example.claimshub.fnol;

import org.springframework.stereotype.Component;

import com.otterworks.insurance.claimshub.triage.TriageEvaluator;
import com.otterworks.insurance.claimshub.triage.TriageFactsReader;

/** The Call_Rules shape over the ClaimTriage rules table: the facts document is evaluated, not looked up. */
@Component
public class RulesTableTriage implements ClaimTriage {

    private final TriageEvaluator evaluator;

    public RulesTableTriage(TriageEvaluator evaluator) {
        this.evaluator = evaluator;
    }

    @Override
    public TriageResult evaluate(String claimNumber, String triageFacts) {
        var result = evaluator.evaluate(TriageFactsReader.read(triageFacts));
        if (claimNumber != null && !claimNumber.equals(result.claimNumber())) {
            throw new IllegalStateException("TriageFacts carry claim " + result.claimNumber() + ", instance is " + claimNumber);
        }
        return new TriageResult(result.outcome(), result.reasons());
    }
}
