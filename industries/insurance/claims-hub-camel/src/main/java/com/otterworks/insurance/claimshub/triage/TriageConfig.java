package com.otterworks.insurance.claimshub.triage;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.io.Resource;

@Configuration
public class TriageConfig {

    @Bean
    public RulesTable claimTriageRules(@Value("${claimshub.triage.rules-table}") Resource table) {
        return RulesTable.load(table);
    }

    @Bean
    public TriageEvaluator triageEvaluator(RulesTable claimTriageRules) {
        return new TriageEvaluator(claimTriageRules);
    }
}
