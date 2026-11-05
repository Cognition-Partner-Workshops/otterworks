package com.bank.rates;

import java.io.IOException;
import java.net.URI;
import java.net.http.*;
import java.time.Duration;
import java.time.Instant;
import java.util.*;

final class S3Storage extends Storage {
    private final String location;
    private final String[] parts;
    private final Map<String, String> env;
    private final HttpClient client = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(30)).build();

    S3Storage(String location) { this(location, System.getenv()); }
    S3Storage(String location, Map<String, String> env) {
        this.location = location;
        this.parts = s3Location(location);
        this.env = env;
    }
    byte[] read(String name) throws IOException { return request("GET", name, new byte[0]); }
    void write(String name, byte[] data) throws IOException { request("PUT", name, data); }
    public String toString() { return location; }

    private byte[] request(String method, String name, byte[] data) throws IOException {
        String region = env.getOrDefault("AWS_REGION", "us-east-1");
        String endpoint = env.getOrDefault("S3_ENDPOINT", "https://s3." + region + ".amazonaws.com");
        URI base = URI.create(endpoint);
        if (!("https".equals(base.getScheme()) || "http".equals(base.getScheme()))
                || base.getHost() == null || base.getUserInfo() != null || base.getQuery() != null || base.getFragment() != null) {
            throw new IllegalArgumentException("invalid S3_ENDPOINT");
        }
        String path = base.getPath().replaceAll("/+$", "") + "/" + parts[0] + "/"
                + (parts[1].isEmpty() ? "" : parts[1] + "/") + name;
        URI uri = URI.create(base.getScheme() + "://" + base.getRawAuthority() + SigV4.encodePath(path));
        String access = env.get("AWS_ACCESS_KEY_ID"), secret = env.get("AWS_SECRET_ACCESS_KEY");
        if (access == null || secret == null) throw new IOException("S3 credentials are required");
        Map<String, String> headers = new TreeMap<>();
        headers.put("host", uri.getRawAuthority());
        headers.put("x-amz-date", SigV4.timestamp(Instant.now()));
        headers.put("x-amz-content-sha256", SigV4.hash(data));
        if (env.containsKey("AWS_SESSION_TOKEN")) headers.put("x-amz-security-token", env.get("AWS_SESSION_TOKEN"));
        HttpRequest.Builder request = HttpRequest.newBuilder(uri).timeout(Duration.ofSeconds(60));
        headers.forEach((k, v) -> { if (!k.equals("host")) request.header(k, v); });
        request.header("Authorization", SigV4.authorization(method, uri.getRawPath(), headers,
                SigV4.hash(data), region, access, secret));
        request.method(method, HttpRequest.BodyPublishers.ofByteArray(data));
        try {
            HttpResponse<byte[]> response = client.send(request.build(), HttpResponse.BodyHandlers.ofByteArray());
            if (method.equals("GET") && response.statusCode() == 404) return null;
            if (response.statusCode() / 100 != 2) throw new IOException("S3 " + method + " failed: HTTP " + response.statusCode());
            return response.body();
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new IOException("S3 request interrupted", e);
        }
    }
}
