package com.bank.kyc;

import java.io.IOException;
import java.io.InputStream;
import java.nio.file.*;
import java.util.List;
import java.util.stream.Collectors;
import java.util.stream.Stream;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;

@Component
@ConditionalOnProperty(name = "kyc.storage", havingValue = "file", matchIfMissing = true)
public class FileBlobStore implements BlobStore {
    private final Path root;

    public FileBlobStore(@Value("${kyc.upload-dir}") String uploadDir) {
        root = Paths.get(uploadDir);
    }

    @Override
    public long put(String key, InputStream body, long size) throws IOException {
        Path destination = root.resolve(key);
        Files.createDirectories(destination.getParent());
        return Files.copy(body, destination, StandardCopyOption.REPLACE_EXISTING);
    }

    @Override
    public List<String> list(String customer) throws IOException {
        Path dir = root.resolve(customer);
        if (!Files.isDirectory(dir)) return List.of();
        try (Stream<Path> paths = Files.list(dir)) {
            return paths.map(p -> p.getFileName().toString()).sorted().collect(Collectors.toList());
        }
    }

    @Override
    public boolean healthy() {
        try {
            Files.createDirectories(root);
            return Files.isDirectory(root);
        } catch (IOException | SecurityException e) {
            return false;
        }
    }
}
