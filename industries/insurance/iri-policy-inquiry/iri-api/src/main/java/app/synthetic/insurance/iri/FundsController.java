package app.synthetic.insurance.iri;

import java.time.Instant;
import java.util.List;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class FundsController {
    static final int DEFAULT_LIMIT = 50;
    static final int MAX_LIMIT = 200;

    private final FundsRepository repository;
    private final FundsMapper mapper;

    public FundsController(FundsRepository repository, FundsMapper mapper) {
        this.repository = repository;
        this.mapper = mapper;
    }

    @GetMapping("/v1/policies/{policyNumber}/funds")
    public FundsMapper.PolicyFunds funds(@PathVariable String policyNumber,
                                         @RequestParam(required = false) String startIndex,
                                         @RequestParam(required = false) String limit) {
        long contract = PolicyNumbers.parse(policyNumber);
        int start = paging("startIndex", startIndex, 0, 0, Integer.MAX_VALUE);
        int size = paging("limit", limit, DEFAULT_LIMIT, 1, MAX_LIMIT);
        List<FundsRepository.FundRow> rows = repository.funds(contract);
        if (rows.isEmpty()) {
            throw new NotFound("Policy funds not found");
        }
        return mapper.map(rows, start, size);
    }

    private static int paging(String name, String value, int fallback, int min, int max) {
        if (value == null) {
            return fallback;
        }
        if (!value.matches("[0-9]{1,10}") || Long.parseLong(value) < min || Long.parseLong(value) > max) {
            throw new InvalidPaging(name + " must be an integer between " + min + " and " + max);
        }
        return Integer.parseInt(value);
    }

    // S-funds-3: Error.code for invalid paging parameters awaits confirmation.
    @ExceptionHandler(InvalidPaging.class)
    public ResponseEntity<ErrorBody> invalidPaging(InvalidPaging exception) {
        return ResponseEntity.badRequest()
                .body(new ErrorBody("policy.inquiry.invalidPaging", exception.getMessage(), Instant.now()));
    }

    static class InvalidPaging extends RuntimeException {
        InvalidPaging(String message) {
            super(message);
        }
    }
}
