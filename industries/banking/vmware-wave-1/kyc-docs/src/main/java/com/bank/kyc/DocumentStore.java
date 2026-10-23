package com.bank.kyc;

import java.io.IOException;
import java.io.InputStream;
import java.nio.file.*;
import java.time.Instant;
import java.util.*;
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
        String name = kind + "-" + Instant.now().toEpochMilli() + ext;
        long size = Files.copy(body, dir.resolve(name), StandardCopyOption.REPLACE_EXISTING);
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("customer", customer);
        out.put("kind", kind);
        out.put("file", name);
        out.put("bytes", size);
        return out;
    }

    public List<String> list(String customer) throws IOException {
        if (!CUSTOMER.matcher(customer).matches()) throw new IllegalArgumentException("bad customer id");
        Path dir = root.resolve(customer);
        if (!Files.isDirectory(dir)) return List.of();
        try (Stream<Path> s = Files.list(dir)) {
            return s.map(p -> p.getFileName().toString()).sorted().collect(Collectors.toList());
        }
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
