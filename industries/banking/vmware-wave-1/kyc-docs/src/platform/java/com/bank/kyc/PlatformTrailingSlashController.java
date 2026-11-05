package com.bank.kyc;

import java.io.IOException;
import java.util.List;
import java.util.Map;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

@RestController
@RequestMapping("/documents")
public class PlatformTrailingSlashController {
    private final DocumentController documents;

    public PlatformTrailingSlashController(DocumentController documents) {
        this.documents = documents;
    }

    @GetMapping("/{customer}/")
    public List<String> list(@PathVariable String customer) throws IOException {
        return documents.list(customer);
    }

    @PostMapping("/{customer}/")
    public ResponseEntity<Map<String, Object>> upload(@PathVariable String customer, @RequestParam String kind,
                                                      @RequestParam("file") MultipartFile file) throws IOException {
        return documents.upload(customer, kind, file);
    }

    @ExceptionHandler(IllegalArgumentException.class)
    public ResponseEntity<Map<String, String>> bad(IllegalArgumentException e) {
        return documents.bad(e);
    }
}
