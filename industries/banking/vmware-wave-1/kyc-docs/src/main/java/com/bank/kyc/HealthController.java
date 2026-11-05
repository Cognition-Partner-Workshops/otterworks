package com.bank.kyc;

import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class HealthController {

    private final DocumentStore store;

    public HealthController(DocumentStore store) {
        this.store = store;
    }

    @GetMapping("/health")
    public ResponseEntity<Map<String, String>> health() {
        if (store.writable()) return ResponseEntity.ok(Map.of("status", "UP"));
        return ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE).body(Map.of("status", "DOWN"));
    }
}
