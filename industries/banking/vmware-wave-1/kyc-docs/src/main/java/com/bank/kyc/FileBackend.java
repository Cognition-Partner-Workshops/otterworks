package com.bank.kyc;

import java.io.IOException;
import java.io.InputStream;
import java.nio.file.*;
import java.util.List;
import java.util.stream.Collectors;
import java.util.stream.Stream;

/** Documents under a local directory: {@code <root>/<customer>/<name>}. */
public class FileBackend implements DocumentBackend {

    private final Path root;

    public FileBackend(String root) {
        this.root = Paths.get(root);
    }

    @Override
    public long put(String customer, String name, InputStream body) throws IOException {
        Path dir = root.resolve(customer);
        Files.createDirectories(dir);
        return Files.copy(body, dir.resolve(name), StandardCopyOption.REPLACE_EXISTING);
    }

    @Override
    public List<String> list(String customer) throws IOException {
        Path dir = root.resolve(customer);
        if (!Files.isDirectory(dir)) return List.of();
        try (Stream<Path> s = Files.list(dir)) {
            return s.map(p -> p.getFileName().toString()).collect(Collectors.toList());
        }
    }

    @Override
    public void check() throws IOException {
        Files.createDirectories(root);
        if (!Files.isWritable(root)) throw new IOException(root + " is not writable");
    }
}
