package com.bank.kyc;

import static org.junit.jupiter.api.Assertions.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

import jakarta.servlet.RequestDispatcher;
import java.nio.file.Path;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.boot.web.error.ErrorAttributeOptions;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.context.request.ServletWebRequest;

class PlatformCompatibilityTest {
    @TempDir Path tmp;

    @Test
    void defaultErrorsPreserveVmFieldOrderAndTimestampFormat() {
        for (int status : new int[]{400, 404, 500}) {
            MockHttpServletRequest request = new MockHttpServletRequest();
            request.setAttribute(RequestDispatcher.ERROR_STATUS_CODE, status);
            request.setAttribute(RequestDispatcher.ERROR_REQUEST_URI, "/documents/");
            Map<String, Object> result = new PlatformErrorAttributes()
                    .getErrorAttributes(new ServletWebRequest(request), ErrorAttributeOptions.defaults());
            assertEquals(List.of("timestamp", "status", "error", "message", "path"), List.copyOf(result.keySet()));
            assertTrue(((String) result.get("timestamp")).matches(
                    "[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\\.[0-9]{3}\\+00:00"));
            assertEquals("", result.get("message"));
            assertEquals(status, result.get("status"));
            assertEquals("/documents/", result.get("path"));
        }
    }

    @Test
    void trailingSlashKeepsListAndValidationResponses() throws Exception {
        MockMvc mvc = MockMvcBuilders.standaloneSetup(new PlatformTrailingSlashController(
                new DocumentController(new DocumentStore(new FileBlobStore(tmp.toString()))))).build();
        mvc.perform(get("/documents/HG611000001/")).andExpect(status().isOk())
                .andExpect(content().contentType("application/json")).andExpect(content().string("[]"));
        mvc.perform(get("/documents/bad/")).andExpect(status().isBadRequest())
                .andExpect(content().string("{\"error\":\"bad customer id\"}"));
    }
}
