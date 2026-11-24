package com.otterworks.rating.controller;

import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.ObjectReader;
import com.otterworks.rating.audit.QuoteAuditStore;
import com.otterworks.rating.config.RatingProperties;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.NoSuchFileException;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.Base64;
import java.util.List;
import java.util.regex.Pattern;
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

    private static final Pattern TABLE_NAME = Pattern.compile("[A-Za-z0-9_-]+(?:\\.[A-Za-z0-9_-]+)*");
    private static final ObjectReader PARKED_QUOTE_READER = new ObjectMapper().reader()
            .with(DeserializationFeature.FAIL_ON_TRAILING_TOKENS);

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
        if (!TABLE_NAME.matcher(name).matches()) {
            return ResponseEntity.badRequest().build();
        }
        try {
            Path base = Path.of(properties.tablesDir()).toRealPath();
            Path file = base.resolve(name).toRealPath();
            if (!withinTablesDir(base, file)) {
                return ResponseEntity.badRequest().build();
            }
            return ResponseEntity.ok(Files.readString(file));
        } catch (NoSuchFileException e) {
            return ResponseEntity.notFound().build();
        }
    }

    static boolean withinTablesDir(Path base, Path file) {
        return file.startsWith(base);
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
            if (isLegacySerializedFormat(bytes)) {
                return ResponseEntity.badRequest().contentType(MediaType.TEXT_PLAIN)
                        .body("Unsupported parked quote format: serialized Java objects are no longer accepted; "
                                + "park the quote as JSON.");
            }
            JsonNode reference = PARKED_QUOTE_READER.readTree(bytes).path("reference");
            return reference.isTextual()
                    ? ResponseEntity.ok(reference.textValue())
                    : ResponseEntity.badRequest().build();
        } catch (IOException | IllegalArgumentException e) {
            return ResponseEntity.badRequest().build();
        }
    }

    static boolean isLegacySerializedFormat(byte[] bytes) {
        return bytes.length >= 2 && bytes[0] == (byte) 0xAC && bytes[1] == (byte) 0xED;
    }
}
