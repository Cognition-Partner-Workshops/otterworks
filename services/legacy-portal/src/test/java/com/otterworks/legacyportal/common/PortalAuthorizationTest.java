package com.otterworks.legacyportal.common;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.transaction.annotation.Transactional;

/**
 * Regression tests for the user-keyed routes: identity comes from the bearer token, never from
 * the path, query string or body. Transactional so the rows it writes to the shared in-memory
 * H2 roll back and do not leak into the {@code @DataJpaTest} service tests.
 */
@SpringBootTest
@AutoConfigureMockMvc
@Transactional
class PortalAuthorizationTest {

    private static final String PREFS_BODY =
            "{\"theme\":\"dark\",\"locale\":\"fr-FR\",\"emailNotifications\":false}";

    @Autowired private MockMvc mockMvc;

    private static String asUser(String userId) {
        return TestTokens.bearer(TestTokens.accessToken(userId, "USER"));
    }

    private static String asAdmin() {
        return TestTokens.bearer(TestTokens.accessToken("admin-1", "ADMIN", "USER"));
    }

    @Test
    void preferencesRequireBearerToken() throws Exception {
        mockMvc.perform(get("/api/preferences/u1"))
                .andExpect(status().isUnauthorized())
                .andExpect(header().string(HttpHeaders.WWW_AUTHENTICATE, "Bearer"));

        mockMvc.perform(
                        put("/api/preferences/u1")
                                .header(HttpHeaders.AUTHORIZATION, "Bearer not-a-jwt")
                                .contentType(MediaType.APPLICATION_JSON)
                                .content(PREFS_BODY))
                .andExpect(status().isUnauthorized());
    }

    @Test
    void preferencesOfAnotherUserAreForbidden() throws Exception {
        mockMvc.perform(get("/api/preferences/victim").header(HttpHeaders.AUTHORIZATION, asUser("u1")))
                .andExpect(status().isForbidden());

        mockMvc.perform(
                        put("/api/preferences/victim")
                                .header(HttpHeaders.AUTHORIZATION, asUser("u1"))
                                .contentType(MediaType.APPLICATION_JSON)
                                .content(PREFS_BODY))
                .andExpect(status().isForbidden());

        mockMvc.perform(get("/api/preferences/victim").header(HttpHeaders.AUTHORIZATION, asUser("victim")))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.theme").value("light"));
    }

    @Test
    void ownerAndAdminCanReadAndWritePreferences() throws Exception {
        mockMvc.perform(
                        put("/api/preferences/owner")
                                .header(HttpHeaders.AUTHORIZATION, asUser("owner"))
                                .contentType(MediaType.APPLICATION_JSON)
                                .content(PREFS_BODY))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.userId").value("owner"))
                .andExpect(jsonPath("$.theme").value("dark"));

        mockMvc.perform(get("/api/preferences/owner").header(HttpHeaders.AUTHORIZATION, asAdmin()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.theme").value("dark"));
    }

    @Test
    void feedbackRequiresBearerToken() throws Exception {
        mockMvc.perform(get("/api/feedback")).andExpect(status().isUnauthorized());

        mockMvc.perform(
                        post("/api/feedback")
                                .contentType(MediaType.APPLICATION_JSON)
                                .content("{\"rating\":5,\"message\":\"great\"}"))
                .andExpect(status().isUnauthorized());
    }

    @Test
    void feedbackIsAttributedToCallerNotBody() throws Exception {
        mockMvc.perform(
                        post("/api/feedback")
                                .header(HttpHeaders.AUTHORIZATION, asUser("author"))
                                .contentType(MediaType.APPLICATION_JSON)
                                .content("{\"userId\":\"victim\",\"rating\":5,\"message\":\"spoofed\"}"))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.userId").value("author"));

        mockMvc.perform(get("/api/feedback").header(HttpHeaders.AUTHORIZATION, asUser("author")))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$[0].userId").value("author"))
                .andExpect(jsonPath("$[0].message").value("spoofed"));

        mockMvc.perform(
                        get("/api/feedback?userId=author")
                                .header(HttpHeaders.AUTHORIZATION, asUser("victim")))
                .andExpect(status().isForbidden());

        mockMvc.perform(
                        get("/api/feedback?userId=author").header(HttpHeaders.AUTHORIZATION, asAdmin()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$[0].userId").value("author"));
    }

    @Test
    void averageRatingStaysPublic() throws Exception {
        mockMvc.perform(get("/api/feedback/average-rating")).andExpect(status().isOk());
    }
}
