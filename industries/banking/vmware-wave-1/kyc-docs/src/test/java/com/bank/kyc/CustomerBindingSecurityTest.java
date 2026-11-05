package com.bank.kyc;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.security.test.context.support.WithMockUser;
import org.springframework.test.web.servlet.MockMvc;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest(properties = {"server.ssl.enabled=false", "logging.file.name=",
        "kyc.auth.uploader.username=synthetic-uploader", "kyc.auth.reviewer.username=synthetic-reviewer",
        "kyc.auth.uploader.customers=", "kyc.auth.reviewer.customers= *, bad-id, lowercase "})
@AutoConfigureMockMvc
class CustomerBindingSecurityTest {
    @Autowired
    MockMvc mvc;

    @MockBean
    DocumentStore store;

    private void assertDenied() throws Exception {
        mvc.perform(get("/documents/TESTCUST0001"))
                .andExpect(status().isForbidden()).andExpect(content().string("{\"error\":\"forbidden\"}"));
        mvc.perform(multipart("/documents/TESTCUST0001")
                .file(new MockMultipartFile("file", "a.pdf", "application/pdf", new byte[1]))
                .param("kind", "passport"))
                .andExpect(status().isForbidden()).andExpect(content().string("{\"error\":\"forbidden\"}"));
        verifyNoInteractions(store);
    }

    @Test
    @WithMockUser(username = "synthetic-uploader", roles = {"UPLOADER", "REVIEWER"})
    void blankBindingGrantsNothing() throws Exception {
        assertDenied();
    }

    @Test
    @WithMockUser(username = "synthetic-reviewer", roles = {"UPLOADER", "REVIEWER"})
    void wildcardAndInvalidBindingsGrantNothing() throws Exception {
        assertDenied();
    }

    @Test
    @WithMockUser(username = "synthetic-unbound", roles = {"UPLOADER", "REVIEWER"})
    void principalWithNoBindingGrantsNothing() throws Exception {
        assertDenied();
    }
}
