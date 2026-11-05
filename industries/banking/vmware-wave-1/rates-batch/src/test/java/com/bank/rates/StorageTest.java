package com.bank.rates;

import org.junit.Test;
import static org.junit.Assert.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;
import com.sun.net.httpserver.HttpServer;
import java.net.InetSocketAddress;

public class StorageTest {
    @Test public void encodesS3Paths() {
        assertEquals("/bucket/a%20b/%2B/%C3%A9", SigV4.encodePath("/bucket/a b/+/é"));
    }
    @Test public void parsesS3Locations() {
        assertArrayEquals(new String[]{"bank-rates", "in/nested"}, Storage.s3Location("s3://bank-rates/in/nested/"));
        assertArrayEquals(new String[]{"bank-rates", ""}, Storage.s3Location("s3://bank-rates"));
        assertArrayEquals(new String[]{"bank-rates", "a b"}, Storage.s3Location("s3://bank-rates/a%20b"));
    }
    @Test public void rejectsInvalidLocations() {
        for (String s : Arrays.asList("s3:///in", "s3://bucket/in?q=x", "s3://user@bucket/in", "s3://bucket:90/in", "s3://bucket/in#x")) {
            try { Storage.s3Location(s); fail(s); } catch (IllegalArgumentException expected) { }
        }
    }
    @Test public void awsDocumentedGetVector() {
        String hash = SigV4.hash(new byte[0]);
        Map<String, String> h = new TreeMap<>();
        h.put("host", "examplebucket.s3.amazonaws.com");
        h.put("range", "bytes=0-9");
        h.put("x-amz-date", "20130524T000000Z");
        h.put("x-amz-content-sha256", hash);
        String auth = SigV4.authorization("GET", "/test.txt", h, hash, "us-east-1", "AKIAIOSFODNN7EXAMPLE",
                "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY");
        assertTrue(auth, auth.endsWith("Signature=f0e8bdb87c964420e857bd35b5d6ed310bd44f0170aba48dd91039c6036bdb41"));
    }
    @Test public void localStorageEmptyMissingAndRoundTrip() throws Exception {
        Path dir = Files.createTempDirectory("rates-test");
        try {
            Storage s = Storage.open(dir.toString());
            assertNull(s.read("missing.csv"));
            s.write("empty.csv", new byte[0]);
            assertArrayEquals(new byte[0], s.read("empty.csv"));
            s.write("rates.csv", "hello\n".getBytes(StandardCharsets.UTF_8));
            assertEquals("hello\n", new String(s.read("rates.csv"), StandardCharsets.UTF_8));
        } finally {
            try (java.util.stream.Stream<Path> paths = Files.walk(dir)) {
                paths.sorted(Comparator.reverseOrder()).forEach(p -> { try { Files.delete(p); } catch (Exception e) { throw new RuntimeException(e); } });
            }
        }
    }
    @Test public void s3HttpMissingEmptyPutAndFailure() throws Exception {
        HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        Map<String, byte[]> objects = new HashMap<>();
        server.createContext("/", e -> {
            String path = e.getRequestURI().getPath();
            byte[] body = e.getRequestBody().readAllBytes();
            if (!SigV4.hash(body).equals(e.getRequestHeaders().getFirst("x-amz-content-sha256"))) {
                e.sendResponseHeaders(400, -1);
            } else if (path.endsWith("error")) {
                e.sendResponseHeaders(403, -1);
            } else if (e.getRequestMethod().equals("PUT")) {
                objects.put(path, body); e.sendResponseHeaders(200, -1);
            } else if (!objects.containsKey(path)) {
                e.sendResponseHeaders(404, -1);
            } else {
                byte[] data = objects.get(path); e.sendResponseHeaders(200, data.length == 0 ? -1 : data.length);
                e.getResponseBody().write(data);
            }
            e.close();
        });
        server.start();
        try {
            Map<String, String> env = new HashMap<>();
            env.put("S3_ENDPOINT", "http://127.0.0.1:" + server.getAddress().getPort());
            env.put("AWS_ACCESS_KEY_ID", "synthetic-access"); env.put("AWS_SECRET_ACCESS_KEY", "synthetic-secret");
            env.put("AWS_SESSION_TOKEN", "synthetic-token");
            Storage s = new S3Storage("s3://bucket/a%20b", env);
            assertNull(s.read("missing"));
            s.write("empty", new byte[0]); assertArrayEquals(new byte[0], s.read("empty"));
            byte[] data = "pair,open\nEURUSD,1.0\n".getBytes(StandardCharsets.UTF_8);
            s.write("rates.csv", data); assertArrayEquals(data, s.read("rates.csv"));
            assertArrayEquals(data, objects.get("/bucket/a b/rates.csv"));
            try { s.read("error"); fail(); } catch (java.io.IOException expected) { assertTrue(expected.getMessage().contains("403")); }
            try { s.write("error", data); fail(); } catch (java.io.IOException expected) { assertTrue(expected.getMessage().contains("403")); }
        } finally { server.stop(0); }
    }
}
