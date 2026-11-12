package app.synthetic.insurance.iri;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class ValuesController {
    private final ValuesRepository repository;
    private final ValuesMapper mapper;

    public ValuesController(ValuesRepository repository,
                            @Value("${iri.provisional.values.withdrawal-source}") String withdrawalSource) {
        this.repository = repository;
        this.mapper = new ValuesMapper(withdrawalSource);
    }

    @GetMapping("/v1/policies/{policyNumber}/values")
    public PolicyValue getPolicyValue(@PathVariable String policyNumber) {
        return repository.find(PolicyNumbers.parse(policyNumber)).map(mapper::map)
                .orElseThrow(() -> new NotFound("Policy not found"));
    }
}
