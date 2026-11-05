package com.bank.kyc;

import java.nio.file.Files;
import java.nio.file.Path;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.BeforeEach;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.SpyBean;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.servlet.MockMvc;
import static org.hamcrest.Matchers.*;
import static org.mockito.Mockito.*;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.httpBasic;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest(properties = {"server.ssl.enabled=false", "logging.file.name="})
@AutoConfigureMockMvc
class DocumentSecurityTest {
    private static final String TEST_UPLOADER = "synthetic-uploader";
    private static final String TEST_REVIEWER = "synthetic-reviewer";
    private static final String TEST_PASSWORD = "synthetic-test-password";

    @Autowired
    MockMvc mvc;

    @SpyBean
    DocumentStore store;

    @BeforeEach
    void resetStorageCalls() {
        clearInvocations(store);
    }

    @DynamicPropertySource
    static void properties(DynamicPropertyRegistry registry) throws Exception {
        Path uploads = Files.createTempDirectory("kyc-security-test-");
        registry.add("kyc.upload-dir", uploads::toString);
        registry.add("kyc.auth.uploader.username", () -> TEST_UPLOADER);
        registry.add("kyc.auth.reviewer.username", () -> TEST_REVIEWER);
        String hash = new BCryptPasswordEncoder().encode(TEST_PASSWORD);
        registry.add("kyc.auth.uploader.password-hash", () -> hash);
        registry.add("kyc.auth.reviewer.password-hash", () -> hash);
        registry.add("kyc.auth.uploader.customers", () -> " TESTCUST0001 , TESTEMPTY0001,*,bad-id ");
        registry.add("kyc.auth.reviewer.customers", () -> " TESTCUST0001 , TESTEMPTY0001,*,bad-id ");
    }

    private MockMultipartFile pdf() {
        return new MockMultipartFile("file", "a.pdf", "application/pdf", new byte[49]);
    }

    @Test
    void sfind22f920c8UnauthenticatedRequestsAndBadPasswordAreRejected() throws Exception {
        mvc.perform(multipart("/documents/TESTCUST0001").file(pdf()).param("kind", "passport"))
                .andExpect(status().isUnauthorized());
        mvc.perform(get("/documents/TESTCUST0001")).andExpect(status().isUnauthorized());
        mvc.perform(get("/documents/TESTCUST0001").with(httpBasic(TEST_REVIEWER, "wrong")))
                .andExpect(status().isUnauthorized());
        verifyNoInteractions(store);
    }

    @Test
    void sfindEfb96812WrongRolesCannotUploadOrList() throws Exception {
        mvc.perform(multipart("/documents/TESTCUST0001").file(pdf()).param("kind", "passport")
                .with(httpBasic(TEST_REVIEWER, TEST_PASSWORD))).andExpect(status().isForbidden());
        mvc.perform(get("/documents/TESTCUST0001").with(httpBasic(TEST_UPLOADER, TEST_PASSWORD)))
                .andExpect(status().isForbidden());
        verifyNoInteractions(store);
    }

    @Test
    void authorizedUploadAndListingKeepTheirContract() throws Exception {
        mvc.perform(get("/documents/TESTEMPTY0001").with(httpBasic(TEST_REVIEWER, TEST_PASSWORD)))
                .andExpect(status().isOk()).andExpect(content().json("[]"));
        mvc.perform(multipart("/documents/TESTCUST0001").file(pdf()).param("kind", "passport")
                .with(httpBasic(TEST_UPLOADER, TEST_PASSWORD)))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$", aMapWithSize(4)))
                .andExpect(jsonPath("$.customer").value("TESTCUST0001"))
                .andExpect(jsonPath("$.kind").value("passport"))
                .andExpect(jsonPath("$.file", matchesPattern("passport-[0-9]+\\.pdf")))
                .andExpect(jsonPath("$.bytes").value(49));
        mvc.perform(get("/documents/TESTCUST0001").with(httpBasic(TEST_REVIEWER, TEST_PASSWORD)))
                .andExpect(status().isOk()).andExpect(jsonPath("$", hasSize(1)))
                .andExpect(jsonPath("$[0]", matchesPattern("passport-[0-9]+\\.pdf")));
    }

    @Test
    void unlistedAndMalformedCustomersAreDeniedBeforeStorage() throws Exception {
        for (String customer : new String[]{"TESTCUST0002", "bad-id"}) {
            mvc.perform(get("/documents/" + customer).with(httpBasic(TEST_REVIEWER, TEST_PASSWORD)))
                    .andExpect(status().isForbidden()).andExpect(content().string("{\"error\":\"forbidden\"}"));
            mvc.perform(multipart("/documents/" + customer).file(pdf()).param("kind", "passport")
                    .header("X-Customer-Id", "TESTCUST0001")
                    .with(httpBasic(TEST_UPLOADER, TEST_PASSWORD)))
                    .andExpect(status().isForbidden()).andExpect(content().string("{\"error\":\"forbidden\"}"));
        }
        verifyNoInteractions(store);
    }

    @Test
    void authorizedValidationKeeps400Bodies() throws Exception {
        mvc.perform(multipart("/documents/TESTCUST0001").file(pdf()).param("kind", "selfie")
                .with(httpBasic(TEST_UPLOADER, TEST_PASSWORD)))
                .andExpect(status().isBadRequest()).andExpect(content().string("{\"error\":\"unknown document kind\"}"));
    }

    @Test
    void otherRoutesAndMethodsAreDenied() throws Exception {
        mvc.perform(get("/health")).andExpect(status().isUnauthorized());
        mvc.perform(get("/").with(httpBasic(TEST_REVIEWER, TEST_PASSWORD))).andExpect(status().isForbidden());
        mvc.perform(delete("/documents/TESTCUST0001").with(httpBasic(TEST_UPLOADER, TEST_PASSWORD)))
                .andExpect(status().isForbidden());
        verifyNoInteractions(store);
    }
}
