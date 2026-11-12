package app.synthetic.insurance;

import java.util.List;
import java.util.Map;
import org.springframework.dao.DataAccessException;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class InquiryController {
    private final InquiryRepository repository;

    public InquiryController(InquiryRepository repository) {
        this.repository = repository;
    }

    private long contract(String value) {
        if (!value.matches("[0-9]+")) {
            throw new IllegalArgumentException("Invalid contract number");
        }
        return Long.parseLong(value);
    }

    @GetMapping("/pinq/v1/summary/{contractNo}")
    public ResponseEntity<Map<String, String>> summary(@PathVariable String contractNo) {
        return repository.summary(contract(contractNo)).map(LegacyMapper::summary)
                .map(ResponseEntity::ok).orElseGet(this::notFound);
    }

    @GetMapping("/pinq/v1/values/{contractNo}")
    public ResponseEntity<Map<String, String>> values(@PathVariable String contractNo) {
        return repository.values(contract(contractNo)).map(LegacyMapper::values)
                .map(ResponseEntity::ok).orElseGet(this::notFound);
    }

    @GetMapping("/pinq/v1/funds/{contractNo}")
    public ResponseEntity<Map<String, String>> funds(@PathVariable String contractNo) {
        long number = contract(contractNo);
        List<Map<String, Object>> rows = repository.funds(number);
        return rows.isEmpty() ? notFound() : ResponseEntity.ok(LegacyMapper.funds(number, rows));
    }

    @GetMapping("/pinq/v1/contracts")
    public Map<String, String> contracts() {
        List<Long> contracts = repository.contracts();
        Map<String, String> result = LegacyMapper.success();
        result.put("CNTR_CNT", Integer.toString(contracts.size()));
        for (int i = 0; i < contracts.size(); i++) {
            result.put(String.format(java.util.Locale.ROOT, "CNTR_NO_%03d", i + 1), contracts.get(i).toString());
        }
        return result;
    }

    @GetMapping("/health")
    public ResponseEntity<Map<String, String>> health() {
        try {
            repository.ping();
            return ResponseEntity.ok(Map.of("STATUS", "UP", "DB", "UP"));
        } catch (RuntimeException e) {
            return ResponseEntity.status(503).body(Map.of("STATUS", "DOWN", "DB", "DOWN"));
        }
    }

    private ResponseEntity<Map<String, String>> notFound() {
        return ResponseEntity.status(404).body(Map.of("RTN_CD", "04"));
    }

    @ExceptionHandler(IllegalArgumentException.class)
    public ResponseEntity<Map<String, String>> badRequest() {
        return ResponseEntity.badRequest().body(Map.of("RTN_CD", "08"));
    }

    @ExceptionHandler(DataAccessException.class)
    public ResponseEntity<Map<String, String>> unavailable() {
        return ResponseEntity.status(503).body(Map.of("RTN_CD", "96"));
    }
}
