package com.bank.kyc;

import static org.junit.jupiter.api.Assertions.*;

import java.io.ByteArrayInputStream;
import java.nio.file.Path;
import java.nio.file.Files;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class DocumentStoreTest {

    @TempDir
    Path tmp;

    @Test
    void masksCustomerInUploadResponse() throws Exception {
        DocumentStore s = new DocumentStore(tmp.toString());
        Map<String, Object> r = s.save("HG611000001", "passport", "scan.pdf",
                new ByteArrayInputStream(new byte[] { 1 }));
        assertEquals("****0001", r.get("customer"));
        assertTrue(Files.isDirectory(tmp.resolve("HG611000001")));
    }

    @Test
    void repeatedUploadsRetainEveryOriginalDocument() throws Exception {
        DocumentStore s = new DocumentStore(tmp.toString());
        List<String> names = new ArrayList<>();
        for (int i = 0; i < 1000; i++) {
            byte[] content = ("identity document " + i).getBytes(java.nio.charset.StandardCharsets.UTF_8);
            names.add((String) s.save("HG611000001", "passport", "scan.pdf",
                    new ByteArrayInputStream(content)).get("file"));
        }
        assertEquals(1000, s.list("HG611000001").size(), "every upload must be retained, even within one millisecond");
        for (int i = 0; i < names.size(); i++) {
            assertEquals("identity document " + i,
                    Files.readString(tmp.resolve("HG611000001").resolve(names.get(i))));
        }
    }

    @Test
    void listsSameKindUploadsInUploadOrder() throws Exception {
        DocumentStore s = new DocumentStore(tmp.toString());
        List<String> names = new ArrayList<>();
        for (int i = 0; i < 32; i++) {
            names.add((String) s.save("HG611000001", "passport", "scan.pdf",
                    new ByteArrayInputStream(new byte[] { (byte) i })).get("file"));
        }
        assertEquals(names, s.list("HG611000001"));
    }

    @Test
    void savesUnderCustomerAndLists() throws Exception {
        DocumentStore s = new DocumentStore(tmp.toString());
        Map<String, Object> r = s.save("HG611000001", "passport", "Scan.PDF", new ByteArrayInputStream(new byte[42]));
        assertEquals(42L, r.get("bytes"));
        assertTrue(((String) r.get("file")).startsWith("passport-"));
        assertTrue(((String) r.get("file")).endsWith(".pdf"));
        assertEquals(1, s.list("HG611000001").size());
    }

    @Test
    void rejectsPathTricksAndUnknownKinds() {
        DocumentStore s = new DocumentStore(tmp.toString());
        assertThrows(IllegalArgumentException.class,
                () -> s.save("../etc", "passport", "a.pdf", new ByteArrayInputStream(new byte[1])));
        assertThrows(IllegalArgumentException.class,
                () -> s.save("HG611000001", "selfie", "a.pdf", new ByteArrayInputStream(new byte[1])));
        assertEquals(".bin", DocumentStore.extension("run.sh"));
    }
}
