package com.otterworks.legacyportal.userpreferences;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.web.servlet.MockMvc;

@SpringBootTest(properties = {
    "JWT_SECRET=preference-test-secret-at-least-32-bytes",
    "spring.datasource.url=jdbc:h2:mem:preference-access;DB_CLOSE_DELAY=-1;DB_CLOSE_ON_EXIT=FALSE;"
        + "INIT=CREATE SCHEMA IF NOT EXISTS ANNOUNCEMENTS\\\\;CREATE SCHEMA IF NOT EXISTS USER_PREFERENCES\\\\;CREATE SCHEMA IF NOT EXISTS FEEDBACK"
})
@AutoConfigureMockMvc
class PreferenceAccessTest {
    @Autowired private MockMvc mvc;

    static String token(String user) {
        return io.jsonwebtoken.Jwts.builder().subject(user).claim("type", "access")
            .expiration(new java.util.Date(System.currentTimeMillis() + 60000))
            .signWith(io.jsonwebtoken.security.Keys.hmacShaKeyFor("preference-test-secret-at-least-32-bytes".getBytes(java.nio.charset.StandardCharsets.UTF_8)))
            .compact();
    }

    @Test void ownerSucceedsButCrossUserReadAndWriteFail() throws Exception {
        mvc.perform(get("/api/preferences/alice").header("Authorization", "Bearer " + token("alice")))
            .andExpect(status().isOk());
        mvc.perform(get("/api/preferences/bob").header("Authorization", "Bearer " + token("alice")))
            .andExpect(status().isForbidden());
        mvc.perform(put("/api/preferences/bob").header("Authorization", "Bearer " + token("alice"))
            .contentType("application/json").content("{\"theme\":\"dark\",\"locale\":\"en-US\"}"))
            .andExpect(status().isForbidden());
    }

    @Test void anonymousReadIsRejected() throws Exception {
        mvc.perform(get("/api/preferences/alice")).andExpect(status().isUnauthorized());
    }

    @Test void anonymousWriteIsRejected() throws Exception {
        mvc.perform(put("/api/preferences/alice").contentType("application/json")
            .content("{\"theme\":\"dark\",\"locale\":\"en-US\",\"emailNotifications\":true}"))
            .andExpect(status().isUnauthorized());
    }
}
