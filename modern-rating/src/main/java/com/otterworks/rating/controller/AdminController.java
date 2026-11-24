package com.otterworks.rating.controller;

import com.otterworks.rating.audit.QuoteAuditStore;
import com.otterworks.rating.audit.SavedQuote;
import com.otterworks.rating.config.RatingProperties;
import java.nio.file.Files;
import java.nio.file.Path;
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

    /**
     * Takes back a quote the browser parked, so a long session survives a reload. The parked quote
     * arrives as plain JSON bound to {@link SavedQuote}; it is never Java-deserialized.
     */
    @PostMapping(value = "/quotes/restore", consumes = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<String> restore(@RequestBody SavedQuote parked,
            @RequestHeader(value = "X-Support-Key", required = false) String key) {
        if (!allowed(key)) {
            return ResponseEntity.status(403).build();
        }
        if (parked == null || parked.reference() == null || parked.reference().isBlank()) {
            return ResponseEntity.badRequest().build();
        }
        return ResponseEntity.ok(parked.reference());
    }
}
