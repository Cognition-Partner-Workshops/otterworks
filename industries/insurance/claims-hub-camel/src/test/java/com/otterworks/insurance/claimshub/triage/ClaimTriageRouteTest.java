package com.otterworks.insurance.claimshub.triage;

import static org.assertj.core.api.Assertions.assertThat;

import java.nio.file.Files;
import org.apache.camel.Exchange;
import org.apache.camel.ProducerTemplate;
import org.apache.camel.test.spring.junit5.CamelSpringBootTest;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

@CamelSpringBootTest
@SpringBootTest
class ClaimTriageRouteTest {

    @Autowired
    private ProducerTemplate producer;

    @Test
    void routeTriagesAFactsDocumentAndPromotesTheOutcome() throws Exception {
        String xml = Files.readString(Fixture.FACTS.resolve("CLM-2026-100408.xml"));
        Exchange out = producer.request(ClaimTriageRoute.ENDPOINT, e -> e.getMessage().setBody(xml));
        assertThat(out.getException()).isNull();
        assertThat(out.getMessage().getHeader(ClaimTriageRoute.OUTCOME_HEADER)).isEqualTo("LARGE_LOSS");
        TriageResult result = out.getMessage().getBody(TriageResult.class);
        assertThat(result.claimNumber()).isEqualTo("CLM-2026-100408");
        assertThat(result.rulesFired()).containsExactly("LargeLoss");
    }
}
