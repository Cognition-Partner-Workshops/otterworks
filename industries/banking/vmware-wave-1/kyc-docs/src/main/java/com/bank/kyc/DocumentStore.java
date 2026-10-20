package com.bank.kyc;

import java.io.IOException;
import java.io.InputStream;
import java.time.Instant;
import java.util.*;
import java.util.regex.Pattern;
import java.util.stream.Collectors;

public class DocumentStore {

    private static final Pattern CUSTOMER = Pattern.compile("[A-Z0-9]{6,20}");
    private static final Set<String> KINDS = Set.of("passport", "id-card", "proof-of-address", "payslip");

    private final DocumentBackend backend;

    public DocumentStore(String uploadDir) {
        this(new FileBackend(uploadDir));
    }

    public DocumentStore(DocumentBackend backend) {
        this.backend = backend;
    }

    public Map<String, Object> save(String customer, String kind, String originalName, InputStream body)
            throws IOException {
        if (!CUSTOMER.matcher(customer).matches()) throw new IllegalArgumentException("bad customer id");
        if (!KINDS.contains(kind)) throw new IllegalArgumentException("unknown document kind");
        String ext = extension(originalName);
        String name = kind + "-" + Instant.now().toEpochMilli() + ext;
        long size = backend.put(customer, name, body);
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("customer", customer);
        out.put("kind", kind);
        out.put("file", name);
        out.put("bytes", size);
        return out;
    }

    public List<String> list(String customer) throws IOException {
        if (!CUSTOMER.matcher(customer).matches()) throw new IllegalArgumentException("bad customer id");
        return backend.list(customer).stream().sorted().collect(Collectors.toList());
    }

    public void check() throws Exception {
        backend.check();
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
