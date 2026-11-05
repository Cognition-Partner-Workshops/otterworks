package com.bank.kyc;

import java.io.IOException;
import java.util.List;
import java.util.Map;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

@RestController
@RequestMapping("/documents")
public class DocumentController {

    private static final Logger log = LoggerFactory.getLogger(DocumentController.class);
    private final DocumentStore store;
    private final CustomerAuthorizer authorizer;

    public DocumentController(DocumentStore store, CustomerAuthorizer authorizer) {
        this.store = store;
        this.authorizer = authorizer;
    }

    @PostMapping("/{customer}")
    public ResponseEntity<Map<String, Object>> upload(@PathVariable String customer, @RequestParam String kind,
                                                      @RequestParam("file") MultipartFile file,
                                                      Authentication authentication) throws IOException {
        authorizer.requireCustomer(authentication, customer);
        Map<String, Object> saved = store.save(customer, kind, file.getOriginalFilename(), file.getInputStream());
        log.info("stored {} for {} ({} bytes)", kind, customer, saved.get("bytes"));
        return ResponseEntity.status(HttpStatus.CREATED).body(saved);
    }

    @GetMapping("/{customer}")
    public List<String> list(@PathVariable String customer, Authentication authentication) throws IOException {
        authorizer.requireCustomer(authentication, customer);
        return store.list(customer);
    }

    @ExceptionHandler(AccessDeniedException.class)
    public ResponseEntity<Map<String, String>> forbidden() {
        return ResponseEntity.status(HttpStatus.FORBIDDEN).body(Map.of("error", "forbidden"));
    }

    @ExceptionHandler(IllegalArgumentException.class)
    public ResponseEntity<Map<String, String>> bad(IllegalArgumentException e) {
        return ResponseEntity.badRequest().body(Map.of("error", e.getMessage()));
    }
}
