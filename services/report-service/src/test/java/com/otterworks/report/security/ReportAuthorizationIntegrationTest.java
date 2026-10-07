package com.otterworks.report.security;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.otterworks.report.model.Report;
import com.otterworks.report.model.ReportCategory;
import com.otterworks.report.model.ReportRequest;
import com.otterworks.report.model.ReportStatus;
import com.otterworks.report.model.ReportType;
import com.otterworks.report.repository.ReportRepository;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.junit4.SpringRunner;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;
import org.springframework.test.web.servlet.request.RequestPostProcessor;

import java.io.File;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.Date;
import java.util.HashSet;
import java.util.Set;

import static org.hamcrest.Matchers.is;
import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNotEquals;
import static org.junit.Assert.assertTrue;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * Regression tests for report-service authentication and per-report authorization:
 * unauthenticated and forged callers get 401, other users' reports look absent (404),
 * listing is scoped to the caller, ownership comes from the token, and AUDIT_LOG /
 * COMPLIANCE plus the archive/reconciliation APIs are admin-only.
 */
@RunWith(SpringRunner.class)
@SpringBootTest(properties = TestTokens.SECRET_PROPERTY)
@AutoConfigureMockMvc
@ActiveProfiles("test")
public class ReportAuthorizationIntegrationTest {

    private static final String WRONG_SECRET = "attacker-chosen-signing-key-0123456789abcdef0123456789abcdef01";

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @Autowired
    private ReportRepository reportRepository;

    // ---- Authentication ----

    @Test
    public void unauthenticatedRequestsReturn401() throws Exception {
        Long id = saveReport(uniqueUser("victim"), ReportCategory.USAGE_ANALYTICS, ReportStatus.PENDING, null).getId();

        mockMvc.perform(get("/api/v1/reports")).andExpect(status().isUnauthorized());
        mockMvc.perform(get("/api/v1/reports/" + id)).andExpect(status().isUnauthorized());
        mockMvc.perform(get("/api/v1/reports/" + id + "/download")).andExpect(status().isUnauthorized());
        mockMvc.perform(delete("/api/v1/reports/" + id)).andExpect(status().isUnauthorized());
        mockMvc.perform(post("/api/v1/reports").contentType(MediaType.APPLICATION_JSON)
                        .content(json(request(ReportCategory.USAGE_ANALYTICS, "anyone"))))
                .andExpect(status().isUnauthorized());

        assertTrue(reportRepository.findById(id).isPresent());
    }

    @Test
    public void spoofedGatewayIdentityHeaderIsNotTrusted() throws Exception {
        String victim = uniqueUser("victim");
        Long id = saveReport(victim, ReportCategory.USAGE_ANALYTICS, ReportStatus.PENDING, null).getId();

        mockMvc.perform(get("/api/v1/reports/" + id).header("X-User-ID", victim))
                .andExpect(status().isUnauthorized());
        mockMvc.perform(get("/api/v1/reports").header("X-User-ID", victim))
                .andExpect(status().isUnauthorized());
    }

    @Test
    public void forgedRefreshAndExpiredTokensReturn401() throws Exception {
        String user = uniqueUser("user");
        String forged = TestTokens.token(WRONG_SECRET, user, "access", 3600_000L, "ADMIN");
        String refresh = TestTokens.token(TestTokens.SECRET, user, "refresh", 3600_000L, "ADMIN");
        String expired = TestTokens.token(TestTokens.SECRET, user, "access", -60_000L, "ADMIN");
        String unsigned = TestTokens.accessToken(user, "ADMIN").replaceAll("\\.[^.]*$", ".");

        for (String token : new String[] {forged, refresh, expired, unsigned, "not-a-jwt"}) {
            mockMvc.perform(get("/api/v1/reports").with(TestTokens.bearer(token)))
                    .andExpect(status().isUnauthorized());
        }
    }

    @Test
    public void healthEndpointsStayPublic() throws Exception {
        mockMvc.perform(get("/health")).andExpect(status().isOk());
        int archiveHealth = mockMvc.perform(get("/health/archive")).andReturn().getResponse().getStatus();
        assertNotEquals(401, archiveHealth);
        assertNotEquals(403, archiveHealth);
    }

    // ---- Ownership on id-addressed routes ----

    @Test
    public void crossUserReadDownloadAndDeleteLookAbsent() throws Exception {
        String victim = uniqueUser("victim");
        String attacker = uniqueUser("attacker");
        Long id = saveReport(victim, ReportCategory.USAGE_ANALYTICS, ReportStatus.COMPLETED,
                reportFile("victim-secret-contents")).getId();

        mockMvc.perform(get("/api/v1/reports/" + id).with(TestTokens.asUser(attacker)))
                .andExpect(status().isNotFound());
        mockMvc.perform(get("/api/v1/reports/" + id + "/download").with(TestTokens.asUser(attacker)))
                .andExpect(status().isNotFound());
        mockMvc.perform(delete("/api/v1/reports/" + id).with(TestTokens.asUser(attacker)))
                .andExpect(status().isNotFound());

        mockMvc.perform(get("/api/v1/reports/" + id).with(TestTokens.asUser(victim)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.requestedBy", is(victim)));
        mockMvc.perform(get("/api/v1/reports/" + id + "/download").with(TestTokens.asUser(victim)))
                .andExpect(status().isOk())
                .andExpect(content().string("victim-secret-contents"));
        mockMvc.perform(delete("/api/v1/reports/" + id).with(TestTokens.asUser(victim)))
                .andExpect(status().isNoContent());
        assertFalse(reportRepository.findById(id).isPresent());
    }

    @Test
    public void adminCanReadDownloadAndDeleteAnyReport() throws Exception {
        String owner = uniqueUser("owner");
        Long id = saveReport(owner, ReportCategory.STORAGE_SUMMARY, ReportStatus.COMPLETED,
                reportFile("owner-contents")).getId();
        RequestPostProcessor admin = TestTokens.asAdmin(uniqueUser("admin"));

        mockMvc.perform(get("/api/v1/reports/" + id).with(admin)).andExpect(status().isOk());
        mockMvc.perform(get("/api/v1/reports/" + id + "/download").with(admin))
                .andExpect(status().isOk())
                .andExpect(content().string("owner-contents"));
        mockMvc.perform(delete("/api/v1/reports/" + id).with(admin)).andExpect(status().isNoContent());
        assertFalse(reportRepository.findById(id).isPresent());
    }

    // ---- Listing ----

    @Test
    public void listIsScopedToCaller() throws Exception {
        String alice = uniqueUser("alice");
        String bob = uniqueUser("bob");
        Long aliceReport = saveReport(alice, ReportCategory.USAGE_ANALYTICS, ReportStatus.COMPLETED, null).getId();
        Long bobReport = saveReport(bob, ReportCategory.USAGE_ANALYTICS, ReportStatus.COMPLETED, null).getId();

        Set<Long> unfiltered = listIds(mockMvc.perform(get("/api/v1/reports").with(TestTokens.asUser(alice))));
        Set<Long> byStatus = listIds(mockMvc.perform(get("/api/v1/reports").param("status", "COMPLETED")
                .with(TestTokens.asUser(alice))));
        Set<Long> ownId = listIds(mockMvc.perform(get("/api/v1/reports").param("userId", alice)
                .with(TestTokens.asUser(alice))));

        for (Set<Long> ids : java.util.Arrays.asList(unfiltered, byStatus, ownId)) {
            assertTrue(ids.contains(aliceReport));
            assertFalse(ids.contains(bobReport));
        }
        for (Long id : unfiltered) {
            assertEquals(alice, reportRepository.findById(id).get().getRequestedBy());
        }
    }

    @Test
    public void listingAnotherUsersReportsIsForbidden() throws Exception {
        String bob = uniqueUser("bob");
        saveReport(bob, ReportCategory.USAGE_ANALYTICS, ReportStatus.COMPLETED, null);

        mockMvc.perform(get("/api/v1/reports").param("userId", bob).with(TestTokens.asUser(uniqueUser("alice"))))
                .andExpect(status().isForbidden());
    }

    @Test
    public void adminCanListAllReports() throws Exception {
        String alice = uniqueUser("alice");
        String bob = uniqueUser("bob");
        Long aliceReport = saveReport(alice, ReportCategory.USAGE_ANALYTICS, ReportStatus.COMPLETED, null).getId();
        Long bobReport = saveReport(bob, ReportCategory.AUDIT_LOG, ReportStatus.COMPLETED, null).getId();
        RequestPostProcessor admin = TestTokens.asAdmin(uniqueUser("admin"));

        Set<Long> all = listIds(mockMvc.perform(get("/api/v1/reports").with(admin)));
        assertTrue(all.contains(aliceReport));
        assertTrue(all.contains(bobReport));

        Set<Long> bobs = listIds(mockMvc.perform(get("/api/v1/reports").param("userId", bob).with(admin)));
        assertTrue(bobs.contains(bobReport));
        assertFalse(bobs.contains(aliceReport));
    }

    // ---- Ownership assignment on create ----

    @Test
    public void spoofedRequestedByIsReplacedWithCaller() throws Exception {
        String caller = uniqueUser("caller");
        String victim = uniqueUser("victim");

        MvcResult result = mockMvc.perform(post("/api/v1/reports").with(TestTokens.asUser(caller))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(json(request(ReportCategory.USAGE_ANALYTICS, victim))))
                .andExpect(status().isAccepted())
                .andExpect(jsonPath("$.requestedBy", is(caller)))
                .andReturn();
        Long id = objectMapper.readTree(result.getResponse().getContentAsString()).get("id").asLong();

        assertEquals(caller, reportRepository.findById(id).get().getRequestedBy());
        mockMvc.perform(get("/api/v1/reports/" + id).with(TestTokens.asUser(victim)))
                .andExpect(status().isNotFound());
    }

    @Test
    public void createWithoutRequestedByIsAttributedToCaller() throws Exception {
        String caller = uniqueUser("caller");
        mockMvc.perform(post("/api/v1/reports").with(TestTokens.asUser(caller))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(json(request(ReportCategory.STORAGE_SUMMARY, null))))
                .andExpect(status().isAccepted())
                .andExpect(jsonPath("$.requestedBy", is(caller)));
    }

    // ---- Admin-only categories ----

    @Test
    public void nonAdminCannotCreateAuditOrComplianceReports() throws Exception {
        String user = uniqueUser("user");
        for (ReportCategory category : new ReportCategory[] {ReportCategory.AUDIT_LOG, ReportCategory.COMPLIANCE}) {
            mockMvc.perform(post("/api/v1/reports").with(TestTokens.asUser(user))
                            .contentType(MediaType.APPLICATION_JSON)
                            .content(json(request(category, user))))
                    .andExpect(status().isForbidden());
        }
        assertTrue(reportRepository.findByRequestedByOrderByCreatedAtDesc(user).isEmpty());
    }

    @Test
    public void adminCanCreateAuditAndComplianceReports() throws Exception {
        String admin = uniqueUser("admin");
        for (ReportCategory category : new ReportCategory[] {ReportCategory.AUDIT_LOG, ReportCategory.COMPLIANCE}) {
            mockMvc.perform(post("/api/v1/reports").with(TestTokens.asAdmin(admin))
                            .contentType(MediaType.APPLICATION_JSON)
                            .content(json(request(category, null))))
                    .andExpect(status().isAccepted())
                    .andExpect(jsonPath("$.requestedBy", is(admin)));
        }
    }

    @Test
    public void nonAdminCannotReadAdminOnlyCategoryEvenAsOwner() throws Exception {
        String user = uniqueUser("user");
        Long id = saveReport(user, ReportCategory.COMPLIANCE, ReportStatus.COMPLETED,
                reportFile("compliance-export")).getId();

        mockMvc.perform(get("/api/v1/reports/" + id).with(TestTokens.asUser(user)))
                .andExpect(status().isNotFound());
        mockMvc.perform(get("/api/v1/reports/" + id + "/download").with(TestTokens.asUser(user)))
                .andExpect(status().isNotFound());
        assertFalse(listIds(mockMvc.perform(get("/api/v1/reports").with(TestTokens.asUser(user)))).contains(id));
    }

    // ---- Archive / reconciliation ----

    @Test
    public void archiveAndReconciliationRequireAdmin() throws Exception {
        String[] paths = {
            "/api/v1/reports/reconciliation",
            "/api/reports/reconciliation",
            "/api/v1/reports/archive/documents/doc-1",
            "/api/v1/archive/documents/doc-1",
            "/api/archive/documents/doc-1/hash",
        };
        for (String path : paths) {
            mockMvc.perform(get(path)).andExpect(status().isUnauthorized());
            mockMvc.perform(get(path).with(TestTokens.asUser(uniqueUser("user")))).andExpect(status().isForbidden());
            int adminStatus = mockMvc.perform(get(path).with(TestTokens.asAdmin(uniqueUser("admin"))))
                    .andReturn().getResponse().getStatus();
            assertNotEquals(path, 401, adminStatus);
            assertNotEquals(path, 403, adminStatus);
        }
    }

    // ---- Helpers ----

    private static String uniqueUser(String prefix) {
        return prefix + "-" + System.nanoTime();
    }

    private Report saveReport(String owner, ReportCategory category, ReportStatus status, String filePath) {
        Report report = new Report();
        report.setReportName("authz-" + owner);
        report.setCategory(category);
        report.setReportType(ReportType.CSV);
        report.setStatus(status);
        report.setRequestedBy(owner);
        report.setCreatedAt(new Date());
        report.setFilePath(filePath);
        return reportRepository.save(report);
    }

    private static String reportFile(String contents) throws Exception {
        File file = File.createTempFile("report-authz-", ".csv");
        file.deleteOnExit();
        Files.write(file.toPath(), contents.getBytes(StandardCharsets.UTF_8));
        return file.getAbsolutePath();
    }

    private static ReportRequest request(ReportCategory category, String requestedBy) {
        ReportRequest request = new ReportRequest();
        request.setReportName("Authz " + category);
        request.setCategory(category);
        request.setReportType(ReportType.CSV);
        request.setRequestedBy(requestedBy);
        return request;
    }

    private String json(Object value) throws Exception {
        return objectMapper.writeValueAsString(value);
    }

    private Set<Long> listIds(org.springframework.test.web.servlet.ResultActions actions) throws Exception {
        String body = actions.andExpect(status().isOk()).andReturn().getResponse().getContentAsString();
        Set<Long> ids = new HashSet<Long>();
        for (JsonNode node : objectMapper.readTree(body).get("reports")) {
            ids.add(node.get("id").asLong());
        }
        return ids;
    }
}
