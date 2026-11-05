package com.bank.kyc;

import java.util.Map;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class HealthController {
    private final BlobStore blobs;

    public HealthController(BlobStore blobs) {
        this.blobs = blobs;
    }

    @GetMapping("/health")
    public ResponseEntity<Map<String, String>> health() {
        boolean up = blobs.healthy();
        return ResponseEntity.status(up ? 200 : 503).body(Map.of("status", up ? "UP" : "DOWN"));
    }
}
