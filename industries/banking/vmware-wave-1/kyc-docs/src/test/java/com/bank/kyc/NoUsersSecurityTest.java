package com.bank.kyc;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import static org.mockito.Mockito.verifyNoInteractions;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.test.web.servlet.MockMvc;
import static com.bank.kyc.ServiceTokenTestSupport.bearer;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest(properties = {"server.ssl.enabled=false", "logging.file.name=",
        "kyc.auth.uploader.username=", "kyc.auth.uploader.password-hash=",
        "kyc.auth.reviewer.username=", "kyc.auth.reviewer.password-hash="})
@AutoConfigureMockMvc
class NoUsersSecurityTest {
    @Autowired
    MockMvc mvc;

    @MockBean
    DocumentStore store;

    @Test
    void sfind22f920c8NoConfiguredUsersFailsClosedEvenWithCredentials() throws Exception {
        for (String path : new String[]{"/documents/TESTCUST0001", "/health", "/"}) {
            mvc.perform(get(path)).andExpect(status().isUnauthorized());
            mvc.perform(get(path).with(bearer("synthetic-uploader", "synthetic-test-password")))
                    .andExpect(status().isUnauthorized());
        }
        mvc.perform(multipart("/documents/TESTCUST0001")
                .file(new MockMultipartFile("file", "a.pdf", "application/pdf", new byte[1]))
                .param("kind", "passport").with(bearer("synthetic-uploader", "synthetic-test-password")))
                .andExpect(status().isUnauthorized());
        verifyNoInteractions(store);
    }
}
