package app.synthetic.insurance.iri.funds;

import app.synthetic.insurance.iri.shared.ApiException;
import java.math.BigDecimal;
import java.util.List;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class FundsController {
    private final FundsRepository repository;

    public FundsController(FundsRepository repository) {
        this.repository = repository;
    }

    @GetMapping("/v1/policies/{policyNumber}/funds")
    public PolicyFunds getPolicyFunds(@PathVariable String policyNumber,
            @RequestParam(defaultValue = "0") int startIndex, @RequestParam(defaultValue = "50") int limit) {
        if (!policyNumber.matches("[0-9]+") || startIndex < 0 || limit < 1 || limit > 200) {
            throw new IllegalArgumentException("Invalid funds request");
        }
        List<PolicyFunds.Fund> funds = repository.funds(new BigDecimal(policyNumber));
        if (funds.isEmpty()) {
            throw new ApiException(HttpStatus.NOT_FOUND, "Policy funds not found");
        }
        int from = Math.min(startIndex, funds.size());
        int to = from + Math.min(limit, funds.size() - from);
        List<PolicyFunds.Fund> page = funds.subList(from, to);
        return new PolicyFunds(startIndex, page.size(), funds.size(), page);
    }
}
