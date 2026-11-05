package com.bank.kyc;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

import java.nio.file.Path;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

class PlatformControllerTest {
    @TempDir Path tmp;

    @Test
    void healthReflectsStorageReachability() throws Exception {
        BlobStore blobs = mock(BlobStore.class);
        MockMvc mvc = MockMvcBuilders.standaloneSetup(new HealthController(blobs)).build();
        when(blobs.healthy()).thenReturn(true, false);
        mvc.perform(get("/health")).andExpect(status().isOk())
                .andExpect(content().contentType("application/json"))
                .andExpect(content().string("{\"status\":\"UP\"}"));
        mvc.perform(get("/health")).andExpect(status().isServiceUnavailable())
                .andExpect(content().string("{\"status\":\"DOWN\"}"));
    }

    @Test
    void documentResponsesKeepExactWireFormat() throws Exception {
        MockMvc mvc = MockMvcBuilders.standaloneSetup(
                new DocumentController(new DocumentStore(new FileBlobStore(tmp.toString())))).build();
        MockMultipartFile file = new MockMultipartFile("file", "Scan.PDF", "application/pdf", new byte[]{1, 2, 3});
        String body = mvc.perform(multipart("/documents/HG611000001").file(file).param("kind", "passport"))
                .andExpect(status().isCreated()).andExpect(content().contentType("application/json"))
                .andReturn().getResponse().getContentAsString();
        Matcher matcher = Pattern.compile("passport-[0-9]+\\.pdf").matcher(body);
        assertTrue(matcher.find());
        String name = matcher.group();
        assertEquals("{\"customer\":\"HG611000001\",\"kind\":\"passport\",\"file\":\"" + name + "\",\"bytes\":3}", body);
        mvc.perform(get("/documents/HG611000001")).andExpect(status().isOk())
                .andExpect(content().contentType("application/json"))
                .andExpect(content().string("[\"" + name + "\"]"));
        mvc.perform(get("/documents/ABCDEF")).andExpect(content().string("[]"));
        mvc.perform(multipart("/documents/bad").file(file).param("kind", "passport"))
                .andExpect(status().isBadRequest()).andExpect(content().contentType("application/json"))
                .andExpect(content().string("{\"error\":\"bad customer id\"}"));
        mvc.perform(multipart("/documents/HG611000001").file(file).param("kind", "selfie"))
                .andExpect(status().isBadRequest()).andExpect(content().contentType("application/json"))
                .andExpect(content().string("{\"error\":\"unknown document kind\"}"));
        mvc.perform(get("/documents/bad")).andExpect(status().isBadRequest())
                .andExpect(content().string("{\"error\":\"bad customer id\"}"));
    }
}
