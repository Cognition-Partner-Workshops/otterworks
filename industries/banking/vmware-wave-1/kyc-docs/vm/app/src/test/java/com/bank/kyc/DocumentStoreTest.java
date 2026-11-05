package com.bank.kyc;

import static org.junit.jupiter.api.Assertions.*;

import java.io.ByteArrayInputStream;
import java.nio.file.Path;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class DocumentStoreTest {

    @TempDir
    Path tmp;

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
