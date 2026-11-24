package com.otterworks.rating.controller;

import com.otterworks.rating.audit.QuoteAuditStore;
import com.otterworks.rating.audit.SavedQuote;
import com.otterworks.rating.config.RatingProperties;
import java.io.ByteArrayInputStream;
import java.io.ObjectInputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.Base64;
import java.util.List;
import org.springframework.core.env.ConfigurableEnvironment;
import org.springframework.core.env.StandardEnvironment;
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

    private final RatingProperties properties;
    private final QuoteAuditStore audit;
    private final byte[] supportKey;

    public AdminController(RatingProperties properties, QuoteAuditStore audit, ConfigurableEnvironment environment) {
        this.properties = properties;
        this.audit = audit;
        // Read the environment value without expanding placeholders in the key.
        var systemEnvironment = environment.getPropertySources()
                .get(StandardEnvironment.SYSTEM_ENVIRONMENT_PROPERTY_SOURCE_NAME);
        Object configuredKey = systemEnvironment == null ? null : systemEnvironment.getProperty("RATING_SUPPORT_KEY");
        this.supportKey = configuredKey instanceof String key && !key.isBlank()
                ? key.getBytes(StandardCharsets.UTF_8) : new byte[0];
    }

    boolean allowed(String supplied) {
        return supportKey.length > 0 && supplied != null
                && MessageDigest.isEqual(supportKey, supplied.getBytes(StandardCharsets.UTF_8));
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
            @RequestHeader(value = "X-Support-Key", required = false) String key) throws Exception {
        if (!allowed(key)) {
            return ResponseEntity.status(403).build();
        }
        byte[] bytes = Base64.getDecoder().decode(parked.trim().getBytes(StandardCharsets.UTF_8));
        try (ObjectInputStream in = new ObjectInputStream(new ByteArrayInputStream(bytes))) {
            SavedQuote saved = (SavedQuote) in.readObject();
            return ResponseEntity.ok(saved.reference());
        }
    }
}
