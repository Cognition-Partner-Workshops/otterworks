package com.bank.kyc;

import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.time.Instant;
import java.util.*;
import java.util.concurrent.atomic.AtomicLong;
import java.util.regex.Pattern;
import java.util.stream.Collectors;
import java.util.stream.Stream;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

@Component
public class DocumentStore {

    private static final Pattern CUSTOMER = Pattern.compile("[A-Z0-9]{6,20}");
    private static final Set<String> KINDS = Set.of("passport", "id-card", "proof-of-address", "payslip");

    private final Path root;
    private final AtomicLong lastUploadMillis = new AtomicLong();

    public DocumentStore(@Value("${kyc.upload-dir}") String uploadDir) {
        this.root = Paths.get(uploadDir);
    }

    public Map<String, Object> save(String customer, String kind, String originalName, InputStream body)
            throws IOException {
        if (!CUSTOMER.matcher(customer).matches()) throw new IllegalArgumentException("bad customer id");
        if (!KINDS.contains(kind)) throw new IllegalArgumentException("unknown document kind");
        String ext = extension(originalName);
        Path dir = root.resolve(customer);
        Files.createDirectories(dir);
        // Retain each upload indefinitely; no relationship-end date or deletion path exists.
        long timestamp = lastUploadMillis.updateAndGet(last -> Math.max(Instant.now().toEpochMilli(), last + 1));
        String name = kind + "-" + timestamp + "-" + UUID.randomUUID() + ext;
        long size = Files.copy(body, dir.resolve(name));
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("customer", "****" + customer.substring(customer.length() - 4));
        out.put("kind", kind);
        out.put("file", name);
        out.put("bytes", size);
        return out;
    }

    public List<String> list(String customer) throws IOException {
        if (customer.matches("[a-f0-9-]{36}")) {
            final String requestedReference = customer;
            if (!Files.isDirectory(root)) return List.of();
            try (Stream<Path> directories = Files.list(root)) {
                customer = directories.filter(Files::isDirectory)
                    .map(path -> path.getFileName().toString())
                    .filter(name -> CUSTOMER.matcher(name).matches() && reference(name).equals(requestedReference))
                    .findFirst().orElse(null);
            }
            if (customer == null) return List.of();
        }
        if (!CUSTOMER.matcher(customer).matches()) throw new IllegalArgumentException("bad customer id");
        Path dir = root.resolve(customer);
        if (!Files.isDirectory(dir)) return List.of();
        try (Stream<Path> s = Files.list(dir)) {
            return s.map(p -> p.getFileName().toString()).sorted().collect(Collectors.toList());
        }
    }

    static String reference(String customer) {
        return UUID.nameUUIDFromBytes(customer.getBytes(StandardCharsets.UTF_8)).toString();
    }

    static String extension(String name) {
        if (name == null) return ".bin";
        String lower = name.toLowerCase(Locale.ROOT);
        for (String ok : List.of(".pdf", ".jpg", ".jpeg", ".png")) {
            if (lower.endsWith(ok)) return ok;
        }
        return ".bin";
    }
}
