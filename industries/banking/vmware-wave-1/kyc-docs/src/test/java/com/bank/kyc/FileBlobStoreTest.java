package com.bank.kyc;

import static org.junit.jupiter.api.Assertions.*;

import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class FileBlobStoreTest {
    @TempDir Path tmp;

    @Test
    void createsStorageAndReplacesExistingBytes() throws Exception {
        FileBlobStore store = new FileBlobStore(tmp.resolve("uploads").toString());
        assertTrue(store.healthy());
        assertEquals(List.of(), store.list("HG611000001"));
        assertEquals(3, store.put("HG611000001/a.pdf", new ByteArrayInputStream(new byte[]{1, 2, 3}), 3));
        assertEquals(0, store.put("HG611000001/a.pdf", new ByteArrayInputStream(new byte[0]), 0));
        assertEquals(0, Files.size(tmp.resolve("uploads/HG611000001/a.pdf")));
        assertEquals(List.of("a.pdf"), store.list("HG611000001"));
    }

    @Test
    void reportsUnavailableStorageAndPropagatesWriteErrors() throws Exception {
        Path file = Files.createFile(tmp.resolve("not-a-directory"));
        FileBlobStore store = new FileBlobStore(file.toString());
        assertFalse(store.healthy());
        assertThrows(IOException.class,
                () -> store.put("HG611000001/a.pdf", new ByteArrayInputStream(new byte[0]), 0));
    }
}
