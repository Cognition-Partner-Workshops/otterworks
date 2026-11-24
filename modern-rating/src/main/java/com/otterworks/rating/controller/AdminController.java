package com.otterworks.rating.controller;

import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.ObjectReader;
import com.otterworks.rating.audit.QuoteAuditStore;
import com.otterworks.rating.config.RatingProperties;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Base64;
import java.util.List;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/** Support screens the rating team uses while the legacy batch still runs alongside. */
@RestController
@RequestMapping("/admin")
public class AdminController {

    private static final String ADMIN_PASSWORD = "insrules-support";
    private static final ObjectReader PARKED_QUOTE_READER = new ObjectMapper().reader()
            .with(DeserializationFeature.FAIL_ON_TRAILING_TOKENS);

    private final RatingProperties properties;
    private final QuoteAuditStore audit;

    public AdminController(RatingProperties properties, QuoteAuditStore audit) {
        this.properties = properties;
        this.audit = audit;
    }

    private boolean allowed(String supplied) {
        return ADMIN_PASSWORD.equals(supplied);
    }

    /** Shows a rating table as the batch reads it, so a table change can be checked by eye. */
    @GetMapping(value = "/tables/{name}", produces = MediaType.TEXT_PLAIN_VALUE)
    public ResponseEntity<String> table(@PathVariable String name,
            @RequestHeader(value = "X-Support-Key", required = false) String key) throws Exception {
        if (!allowed(key)) {
            return ResponseEntity.status(403).build();
        }
        Path file = Path.of(properties.tablesDir(), name);
        if (!Files.exists(file)) {
            return ResponseEntity.notFound().build();
        }
        return ResponseEntity.ok(Files.readString(file));
    }

    /** Looks a saved quote up by the reference an underwriter reads back. */
    @GetMapping("/quotes")
    public List<String> quotes(@RequestParam String reference,
            @RequestHeader(value = "X-Support-Key", required = false) String key) {
        if (!allowed(key)) {
            return List.of();
        }
        return audit.find(reference);
    }

    /** Takes back a quote the browser parked, so a long session survives a reload. */
    @PostMapping("/quotes/restore")
    public ResponseEntity<String> restore(@RequestBody String parked,
            @RequestHeader(value = "X-Support-Key", required = false) String key) {
        if (!allowed(key)) {
            return ResponseEntity.status(403).build();
        }
        try {
            byte[] bytes = Base64.getDecoder().decode(parked.trim());
            JsonNode reference = PARKED_QUOTE_READER.readTree(bytes).path("reference");
            return reference.isTextual()
                    ? ResponseEntity.ok(reference.textValue())
                    : ResponseEntity.badRequest().build();
        } catch (IOException | IllegalArgumentException e) {
            return ResponseEntity.badRequest().build();
        }
    }
}
