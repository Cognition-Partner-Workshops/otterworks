package com.bank.kyc;

import java.util.Map;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

/** Liveness/readiness for the platform chart: 200 once the document store answers. */
@RestController
public class HealthController {

    private static final Logger log = LoggerFactory.getLogger(HealthController.class);
    private final DocumentStore store;

    public HealthController(DocumentStore store) {
        this.store = store;
    }

    @GetMapping("/health")
    public ResponseEntity<Map<String, String>> health() {
        try {
            store.check();
            return ResponseEntity.ok(Map.of("status", "UP"));
        } catch (Exception e) {
            log.warn("document store not ready: {}", e.toString());
            return ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE).body(Map.of("status", "DOWN"));
        }
    }
}
