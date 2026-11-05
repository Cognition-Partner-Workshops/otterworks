package com.bank.kyc;

import java.io.IOException;
import java.io.InputStream;
import java.time.Instant;
import java.util.*;
import java.util.regex.Pattern;
import org.springframework.stereotype.Component;

@Component
public class DocumentStore {

    private static final Pattern CUSTOMER = Pattern.compile("[A-Z0-9]{6,20}");
    private static final Set<String> KINDS = Set.of("passport", "id-card", "proof-of-address", "payslip");

    private final BlobStore blobs;

    public DocumentStore(BlobStore blobs) {
        this.blobs = blobs;
    }

    public Map<String, Object> save(String customer, String kind, String originalName, InputStream body, long contentLength)
            throws IOException {
        if (!CUSTOMER.matcher(customer).matches()) throw new IllegalArgumentException("bad customer id");
        if (!KINDS.contains(kind)) throw new IllegalArgumentException("unknown document kind");
        String ext = extension(originalName);
        String name = kind + "-" + Instant.now().toEpochMilli() + ext;
        long size = blobs.put(customer + "/" + name, body, contentLength);
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("customer", customer);
        out.put("kind", kind);
        out.put("file", name);
        out.put("bytes", size);
        return out;
    }

    public List<String> list(String customer) throws IOException {
        if (!CUSTOMER.matcher(customer).matches()) throw new IllegalArgumentException("bad customer id");
        List<String> names = new ArrayList<>(blobs.list(customer));
        Collections.sort(names);
        return names;
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
