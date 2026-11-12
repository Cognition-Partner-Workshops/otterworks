package com.otterworks.report.controller;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.otterworks.report.model.ReportCategory;
import com.otterworks.report.model.ReportRequest;
import com.otterworks.report.model.ReportType;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.context.junit4.SpringRunner;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;
import org.springframework.test.web.servlet.request.MockHttpServletRequestBuilder;

import javax.crypto.SecretKey;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.Date;
import java.util.List;

import static org.hamcrest.Matchers.is;
import static org.junit.Assert.assertTrue;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * Ownership / admin authorization with JWT verification enabled (the production
 * configuration, where JWT_SECRET is shared with auth-service and the gateway).
 */
@RunWith(SpringRunner.class)
@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
@TestPropertySource(properties = "otterworks.jwt.secret=" + ReportAuthorizationJwtTest.SECRET)
public class ReportAuthorizationJwtTest {

    static final String SECRET = "report-service-test-jwt-secret-0123456789abcdef";
    private static final String WRONG_SECRET = "report-service-wrong-jwt-secret-0123456789abcdef";

    private static final String OWNER = "owner-user-1";
    private static final String ATTACKER = "attacker-user-2";
    private static final String ADMIN = "admin-user-3";

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @Test
    public void ownerCanReadListAndDownloadOwnReport() throws Exception {
        Long id = createAs(OWNER, "Owner Report");

        mockMvc.perform(as(get("/api/v1/reports/" + id), OWNER))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.requestedBy", is(OWNER)));
        mockMvc.perform(as(get("/api/v1/reports"), OWNER))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.reports[?(@.id == " + id + ")].requestedBy").value(OWNER));
        // 200 once generated, 409 while generating, 404 when generation failed (no backing
        // services in tests): the owner is never turned away for authorization reasons.
        int download = mockMvc.perform(as(get("/api/v1/reports/" + id + "/download"), OWNER))
                .andReturn().getResponse().getStatus();
        assertTrue("owner download status " + download, download != 401 && download != 403);
    }

    @Test
    public void userBCannotDownloadUserAsReport() throws Exception {
        Long id = createAs(OWNER, "Victim Download Report");

        mockMvc.perform(as(get("/api/v1/reports/" + id + "/download"), ATTACKER))
                .andExpect(status().isForbidden());
        mockMvc.perform(as(get("/api/v1/reports/" + id), ATTACKER))
                .andExpect(status().isForbidden());
        mockMvc.perform(as(delete("/api/v1/reports/" + id), ATTACKER))
                .andExpect(status().isForbidden());
        mockMvc.perform(as(get("/api/v1/reports").param("userId", OWNER), ATTACKER))
                .andExpect(status().isForbidden());

        mockMvc.perform(as(get("/api/v1/reports/" + id), OWNER))
                .andExpect(status().isOk());
    }

    @Test
    public void adminCanAccessAnyUsersReport() throws Exception {
        Long id = createAs(OWNER, "Admin Visible Report");

        mockMvc.perform(as(get("/api/v1/reports/" + id), ADMIN, "admin"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.requestedBy", is(OWNER)));
        mockMvc.perform(as(get("/api/v1/reports").param("userId", OWNER), ADMIN, "admin"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.reports[?(@.id == " + id + ")].requestedBy").value(OWNER));
        mockMvc.perform(as(delete("/api/v1/reports/" + id), ADMIN, "admin"))
                .andExpect(status().isNoContent());
    }

    @Test
    public void spoofedGatewayHeaderIsIgnoredWhenJwtVerificationIsOn() throws Exception {
        Long id = createAs(OWNER, "Header Spoof Report");

        // No token, only the gateway identity header: not authenticated.
        mockMvc.perform(get("/api/v1/reports/" + id).header("X-User-ID", OWNER))
                .andExpect(status().isUnauthorized());
        // Attacker token plus a forged header naming the owner: identity comes from the token.
        mockMvc.perform(as(get("/api/v1/reports/" + id), ATTACKER).header("X-User-ID", OWNER))
                .andExpect(status().isForbidden());
    }

    @Test
    public void forgedTokensAreRejected() throws Exception {
        Long id = createAs(OWNER, "Forged Token Report");

        String forged = token(OWNER, Arrays.asList("admin"), WRONG_SECRET, "access");
        mockMvc.perform(get("/api/v1/reports/" + id).header("Authorization", "Bearer " + forged))
                .andExpect(status().isUnauthorized());

        String refresh = token(OWNER, Arrays.asList("user"), SECRET, "refresh");
        mockMvc.perform(get("/api/v1/reports/" + id).header("Authorization", "Bearer " + refresh))
                .andExpect(status().isUnauthorized());

        mockMvc.perform(get("/api/v1/reports/" + id).header("Authorization", "Bearer not.a.jwt"))
                .andExpect(status().isUnauthorized());
    }

    // ---- Helpers ----

    private MockHttpServletRequestBuilder as(MockHttpServletRequestBuilder builder, String userId, String... roles) {
        List<String> roleList = roles.length == 0 ? Arrays.asList("user") : Arrays.asList(roles);
        return builder.header("Authorization", "Bearer " + token(userId, roleList, SECRET, "access"));
    }

    private static String token(String subject, List<String> roles, String secret, String type) {
        SecretKey key = Keys.hmacShaKeyFor(secret.getBytes(StandardCharsets.UTF_8));
        Date now = new Date();
        return Jwts.builder()
                .subject(subject)
                .claim("roles", roles)
                .claim("type", type)
                .issuedAt(now)
                .expiration(new Date(now.getTime() + 60_000L))
                .signWith(key)
                .compact();
    }

    private Long createAs(String userId, String name) throws Exception {
        ReportRequest request = new ReportRequest();
        request.setReportName(name);
        request.setCategory(ReportCategory.USAGE_ANALYTICS);
        request.setReportType(ReportType.CSV);
        request.setDateFrom(new Date(System.currentTimeMillis() - 86400000L));
        request.setDateTo(new Date());
        MvcResult result = mockMvc.perform(as(post("/api/v1/reports"), userId)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isAccepted())
                .andExpect(jsonPath("$.requestedBy", is(userId)))
                .andReturn();
        return objectMapper.readTree(result.getResponse().getContentAsString()).get("id").asLong();
    }
}
