package app.synthetic.insurance.iri.values;

import app.synthetic.insurance.iri.shared.ApiException;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/** GET /v1/policies/{policyNumber}/values (operationId getPolicyValue). */
@RestController
public class PolicyValuesController {
    private final PolicyValuesRepository repository;

    public PolicyValuesController(PolicyValuesRepository repository) {
        this.repository = repository;
    }

    @GetMapping(value = "/v1/policies/{policyNumber}/values", produces = "application/json")
    public PolicyValue getPolicyValue(@PathVariable String policyNumber,
                                      @RequestParam(required = false) String associatedFirmId) {
        if (associatedFirmId != null && (associatedFirmId.isEmpty() || associatedFirmId.length() > 65)) {
            throw new IllegalArgumentException("Invalid associatedFirmId");
        }
        return repository.find(contractNumber(policyNumber)).map(PolicyValueMapper::map)
                .orElseThrow(() -> new ApiException(HttpStatus.NOT_FOUND, "Policy values not found"));
    }

    /** Legacy CNTR_NO rule: digits only (RTN_CD 08 otherwise); spec caps the path at 30 characters. */
    static long contractNumber(String policyNumber) {
        if (policyNumber.length() > 30 || !policyNumber.matches("[0-9]+")) {
            throw new IllegalArgumentException("Invalid policy number");
        }
        return Long.parseLong(policyNumber);
    }
}
