package com.bank.kyc;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.io.ByteArrayInputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

class DocumentControllerTest {
    @TempDir
    Path tmp;

    @Test
    void exposesNoDeleteOrOverwriteOperation() throws Exception {
        DocumentStore store = new DocumentStore(tmp.toString());
        byte[] original = new byte[] { 1, 2, 3 };
        String file = (String) store.save("HG611000001", "passport", "id.pdf",
                new ByteArrayInputStream(original)).get("file");
        MockMvc mvc = MockMvcBuilders.standaloneSetup(new DocumentController(store)).build();
        mvc.perform(delete("/documents/HG611000001")).andExpect(status().isMethodNotAllowed());
        mvc.perform(put("/documents/HG611000001")).andExpect(status().isMethodNotAllowed());
        mvc.perform(delete("/documents/HG611000001/" + file)).andExpect(status().isNotFound());
        mvc.perform(put("/documents/HG611000001/" + file)).andExpect(status().isNotFound());
        assertArrayEquals(original, Files.readAllBytes(tmp.resolve("HG611000001").resolve(file)));
    }
}
