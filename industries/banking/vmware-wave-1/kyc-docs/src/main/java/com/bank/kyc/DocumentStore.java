package com.bank.kyc;

import java.io.IOException;
import java.io.InputStream;
import java.nio.file.*;
import java.time.Clock;
import java.util.*;
import java.util.regex.Pattern;
import java.util.stream.Collectors;
import java.util.stream.Stream;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

@Component
public class DocumentStore {

    private static final Pattern CUSTOMER = Pattern.compile("[A-Z0-9]{6,20}");
    private static final Set<String> KINDS = Set.of("passport", "id-card", "proof-of-address", "payslip");
    private static final int MAX_NAME_ATTEMPTS = 1000;

    private final Path root;
    private final Clock clock;

    @Autowired
    public DocumentStore(@Value("${kyc.upload-dir}") String uploadDir) {
        this(uploadDir, Clock.systemUTC());
    }

    DocumentStore(String uploadDir, Clock clock) {
        this.root = Paths.get(uploadDir);
        this.clock = clock;
    }

    public Map<String, Object> save(String customer, String kind, String originalName, InputStream body)
            throws IOException {
        if (!CUSTOMER.matcher(customer).matches()) throw new IllegalArgumentException("bad customer id");
        if (!KINDS.contains(kind)) throw new IllegalArgumentException("unknown document kind");
        String ext = extension(originalName);
        Path dir = root.resolve(customer);
        Files.createDirectories(dir);
        String stem = kind + "-" + clock.millis();
        String name = stem + ext;
        long size = -1;
        for (int n = 1; size < 0; n++) {
            try {
                // Without REPLACE_EXISTING, Files.copy creates the target with CREATE_NEW, so an
                // existing upload is never overwritten and two writers cannot claim the same name.
                size = Files.copy(body, dir.resolve(name));
            } catch (FileAlreadyExistsException taken) {
                if (n >= MAX_NAME_ATTEMPTS) throw new IOException("no free file name for " + stem, taken);
                name = stem + "-" + n + ext;
            }
        }
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
