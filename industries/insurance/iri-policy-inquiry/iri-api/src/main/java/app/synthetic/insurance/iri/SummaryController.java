package app.synthetic.insurance.iri;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class SummaryController {
    private final SummaryRepository repository;
    private final SummaryMapper mapper;

    public SummaryController(SummaryRepository repository, SummaryMapper mapper) {
        this.repository = repository;
        this.mapper = mapper;
    }

    /** getPolicySummary; associatedFirmId is accepted but not applied (S-summary-2). */
    @GetMapping("/v1/policies/{policyNumber}/summary")
    public PolicySummary getPolicySummary(@PathVariable String policyNumber) {
        long contract = PolicyNumbers.parse(policyNumber);
        return mapper.map(repository.find(contract).orElseThrow(() -> new NotFound("Policy not found")));
    }
}
