package com.bank.kyc;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.io.ByteArrayInputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

class DocumentControllerTest {
    @TempDir
    Path tmp;

    @Test
    void uploadReturnsMaskedCustomerAndWorkingDocumentsLink() throws Exception {
        DocumentStore store = new DocumentStore(tmp.toString());
        MockMvc mvc = MockMvcBuilders.standaloneSetup(new DocumentController(store)).build();
        ObjectMapper json = new ObjectMapper();
        String response = mvc.perform(multipart("/documents/HG611000001")
                .file(new MockMultipartFile("file", "id.pdf", "application/pdf", new byte[] { 1, 2, 3 }))
                .param("kind", "passport"))
                .andExpect(status().isCreated()).andReturn().getResponse().getContentAsString();
        JsonNode saved = json.readTree(response);
        assertEquals("****0001", saved.path("customer").asText());
        assertEquals("/documents/HG611000001", saved.path("documentsUrl").asText());
        String listed = mvc.perform(get(saved.path("documentsUrl").asText()))
                .andExpect(status().isOk()).andReturn().getResponse().getContentAsString();
        assertEquals(json.createArrayNode().add(saved.path("file").asText()), json.readTree(listed));
    }

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
