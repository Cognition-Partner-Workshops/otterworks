package com.bank.kyc;

import static org.junit.jupiter.api.Assertions.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;
import java.io.*;
import java.nio.file.*;
import java.util.*;
import com.fasterxml.jackson.databind.*;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

class DisclosureTest {
    private Path directory() throws IOException {
        return Files.createDirectories(Paths.get("target", "fs09_" + UUID.randomUUID()));
    }

    @Test
    void documentLinksDoNotExposeAccountsAndStillListUploads() throws Exception {
        MockMvc mvc = MockMvcBuilders.standaloneSetup(new DocumentController(new DocumentStore(directory().toString()))).build();
        String body = mvc.perform(multipart("/documents/HG611000001")
                .file(new MockMultipartFile("file", "id.pdf", "application/pdf", new byte[] {1}))
                .param("kind", "passport")).andExpect(status().isCreated()).andReturn().getResponse().getContentAsString();
        assertFalse(body.contains("HG611000001"), "Upload response must not expose accounts in URLs");
        ObjectMapper json = new ObjectMapper();
        JsonNode saved = json.readTree(body);
        String list = mvc.perform(get(saved.path("documentsUrl").asText())).andExpect(status().isOk())
                .andReturn().getResponse().getContentAsString();
        assertEquals(saved.path("file").asText(), json.readTree(list).get(0).asText());
    }

    @Test
    void storageErrorsReturnGenericResponsesAndUnknownReferencesAreEmpty() throws Exception {
        DocumentStore broken = new DocumentStore(directory().toString()) {
            public List<String> list(String customer) throws IOException {
                throw new IOException("HG611000001");
            }
        };
        MockMvc mvc = MockMvcBuilders.standaloneSetup(new DocumentController(broken)).build();
        String body = mvc.perform(get("/documents/HG611000001")).andExpect(status().isInternalServerError())
                .andReturn().getResponse().getContentAsString();
        assertFalse(body.contains("HG611000001"));
        mvc = MockMvcBuilders.standaloneSetup(new DocumentController(new DocumentStore(directory().toString()))).build();
        String empty = mvc.perform(get("/documents/11111111-1111-1111-1111-111111111111")).andExpect(status().isOk())
                .andReturn().getResponse().getContentAsString();
        assertEquals("[]", empty);
    }
}
