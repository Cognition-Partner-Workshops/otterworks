package com.bank.rates;

import java.io.IOException;
import java.net.URI;
import java.nio.file.*;

abstract class Storage {
    abstract byte[] read(String name) throws IOException;
    abstract void write(String name, byte[] data) throws IOException;

    static Storage open(String location) {
        if (location.startsWith("s3://")) return new S3Storage(location);
        Path dir = Paths.get(location);
        return new Storage() {
            byte[] read(String name) throws IOException {
                Path path = dir.resolve(name);
                return Files.exists(path) ? Files.readAllBytes(path) : null;
            }
            void write(String name, byte[] data) throws IOException {
                Files.createDirectories(dir);
                Path tmp = dir.resolve("." + name.replace(".csv", ".tmp"));
                Files.write(tmp, data);
                Files.move(tmp, dir.resolve(name), StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING);
            }
            public String toString() { return dir.toString(); }
        };
    }

    static String[] s3Location(String location) {
        URI uri = URI.create(location);
        if (!"s3".equals(uri.getScheme()) || uri.getHost() == null || uri.getPort() != -1
                || uri.getUserInfo() != null || uri.getQuery() != null || uri.getFragment() != null) {
            throw new IllegalArgumentException("invalid S3 location: " + location);
        }
        String prefix = uri.getPath().replaceFirst("^/", "").replaceAll("/+$", "");
        return new String[] {uri.getHost(), prefix};
    }
}
