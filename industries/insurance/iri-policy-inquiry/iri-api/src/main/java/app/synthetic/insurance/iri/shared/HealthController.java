package app.synthetic.insurance.iri.shared;

import java.util.Map;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class HealthController {
    private final JdbcTemplate jdbc;

    public HealthController(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    @GetMapping("/health")
    public ResponseEntity<Map<String, String>> health() {
        try {
            if (!Integer.valueOf(1).equals(jdbc.queryForObject("SELECT 1 FROM dual", Integer.class))) {
                throw new IllegalStateException("Database health check failed");
            }
            return ResponseEntity.ok(Map.of("STATUS", "UP", "DB", "UP"));
        } catch (RuntimeException error) {
            return ResponseEntity.status(503).body(Map.of("STATUS", "DOWN", "DB", "DOWN"));
        }
    }
}
