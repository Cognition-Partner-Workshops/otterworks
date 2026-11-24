package com.otterworks.insurance.claimshub.triage;

import org.apache.camel.builder.RouteBuilder;
import org.springframework.stereotype.Component;

/**
 * The FnolIntake orchestration's Call Rules shape: a TriageFacts document in, the triage result
 * out, with the outcome on the {@code TriageOutcome} header the way BizTalk promoted it.
 */
@Component
public class ClaimTriageRoute extends RouteBuilder {

    public static final String ENDPOINT = "direct:claimTriage";
    public static final String OUTCOME_HEADER = "TriageOutcome";

    private final TriageEvaluator evaluator;

    public ClaimTriageRoute(TriageEvaluator evaluator) {
        this.evaluator = evaluator;
    }

    @Override
    public void configure() {
        from(ENDPOINT).routeId("claimTriage")
                .process(exchange -> {
                    String xml = exchange.getMessage().getMandatoryBody(String.class);
                    TriageResult result = evaluator.evaluate(TriageFactsReader.read(xml));
                    exchange.getMessage().setHeader(OUTCOME_HEADER, result.outcome());
                    exchange.getMessage().setBody(result);
                });
    }
}
