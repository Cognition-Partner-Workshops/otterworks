package com.bank.kyc;

import static org.junit.jupiter.api.Assertions.*;

import java.io.ByteArrayInputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class DocumentStoreConcurrencyTest {

    @TempDir
    Path tmp;

    @Test
    void sameMillisecondUploadGetsSuffixAndKeepsFirstFile() throws Exception {
        Clock frozen = Clock.fixed(Instant.ofEpochMilli(1700000000000L), ZoneOffset.UTC);
        DocumentStore s = new DocumentStore(tmp.toString(), frozen);
        Map<String, Object> first = s.save("HG611000001", "passport", "a.pdf", new ByteArrayInputStream(new byte[3]));
        Map<String, Object> second = s.save("HG611000001", "passport", "b.PDF", new ByteArrayInputStream(new byte[7]));
        Map<String, Object> other = s.save("HG611000001", "payslip", "c.png", new ByteArrayInputStream(new byte[5]));
        assertEquals("passport-1700000000000.pdf", first.get("file"));
        assertEquals("passport-1700000000000-1.pdf", second.get("file"));
        assertEquals("payslip-1700000000000.png", other.get("file"));
        Path dir = tmp.resolve("HG611000001");
        assertEquals(3L, Files.size(dir.resolve("passport-1700000000000.pdf")));
        assertEquals(7L, Files.size(dir.resolve("passport-1700000000000-1.pdf")));
        assertEquals(3, s.list("HG611000001").size());
    }

    @Test
    void backToBackUploadsOfSameKindAreAllKept() throws Exception {
        DocumentStore s = new DocumentStore(tmp.toString());
        int uploads = 500;
        for (int i = 0; i < uploads; i++) {
            s.save("HG611000001", "passport", "a.pdf", new ByteArrayInputStream(new byte[1]));
        }
        assertEquals(uploads, s.list("HG611000001").size(), "no upload overwrote another");
    }

    @Test
    void concurrentUploadsOfSameKindAreAllKept() throws Exception {
        DocumentStore s = new DocumentStore(tmp.toString());
        int uploads = 64;
        ExecutorService pool = Executors.newFixedThreadPool(uploads);
        CountDownLatch go = new CountDownLatch(1);
        List<Future<String>> files = new ArrayList<>();
        try {
            for (int i = 0; i < uploads; i++) {
                byte[] body = new byte[i + 1];
                files.add(pool.submit(() -> {
                    go.await();
                    return (String) s.save("HG611000001", "passport", "a.pdf", new ByteArrayInputStream(body)).get("file");
                }));
            }
            go.countDown();
            Set<String> names = new HashSet<>();
            for (Future<String> f : files) names.add(f.get());
            assertEquals(uploads, names.size(), "each upload gets its own file name");
            assertEquals(uploads, s.list("HG611000001").size(), "no upload overwrote another");
            Set<Long> sizes = new HashSet<>();
            for (String n : names) sizes.add(Files.size(tmp.resolve("HG611000001").resolve(n)));
            assertEquals(uploads, sizes.size(), "every stored file has its own upload's bytes");
        } finally {
            pool.shutdownNow();
        }
    }
}
