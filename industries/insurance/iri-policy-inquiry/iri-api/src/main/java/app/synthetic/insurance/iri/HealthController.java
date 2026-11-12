package app.synthetic.insurance.iri;

import java.util.Map;
import org.springframework.dao.DataAccessException;
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
            jdbc.queryForObject("SELECT 1 FROM dual", Integer.class);
            return ResponseEntity.ok(Map.of("STATUS", "UP", "DB", "UP"));
        } catch (DataAccessException exception) {
            return ResponseEntity.status(503).body(Map.of("STATUS", "DOWN", "DB", "DOWN"));
        }
    }
}
