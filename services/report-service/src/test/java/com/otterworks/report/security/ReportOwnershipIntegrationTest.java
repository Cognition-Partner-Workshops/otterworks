package com.otterworks.report.security;

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

import java.io.File;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.Date;

import static org.hamcrest.Matchers.everyItem;
import static org.hamcrest.Matchers.is;
import static org.junit.Assert.assertNotEquals;
import static org.junit.Assert.assertTrue;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * Regression tests for the report IDOR: every report route used to be permitAll and act on any
 * id, so any caller could walk the sequential ids and read, download or delete every user's
 * reports, list any user's reports, and spoof {@code requestedBy} on create.
 */
@RunWith(SpringRunner.class)
@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
public class ReportOwnershipIntegrationTest {

    private static final String OWNER = "owner-user";
    private static final String ATTACKER = "attacker-user";
    private static final String ADMIN = "admin-user";

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @Autowired
    private ReportRepository reportRepository;

    // ---- authentication ----

    @Test
    public void anonymousRequestsAreRejectedWith401() throws Exception {
        Long id = completedReportOwnedBy(OWNER);

        mockMvc.perform(get("/api/v1/reports/" + id)).andExpect(status().isUnauthorized());
        mockMvc.perform(get("/api/v1/reports/" + id + "/download")).andExpect(status().isUnauthorized());
        mockMvc.perform(delete("/api/v1/reports/" + id)).andExpect(status().isUnauthorized());
        mockMvc.perform(get("/api/v1/reports").param("userId", OWNER)).andExpect(status().isUnauthorized());
        mockMvc.perform(post("/api/v1/reports")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(buildRequest("anon"))))
                .andExpect(status().isUnauthorized());
        mockMvc.perform(get("/api/v1/reports/reconciliation")).andExpect(status().isUnauthorized());
        mockMvc.perform(get("/api/archive/documents/doc-1")).andExpect(status().isUnauthorized());

        assertTrue(reportRepository.findById(id).isPresent());
    }

    @Test
    public void tokenSignedWithAnotherKeyIsRejected() throws Exception {
        Long id = completedReportOwnedBy(OWNER);
        String forged = TestTokens.bearerSignedWith("not-the-real-secret-but-still-32-bytes!", OWNER);

        mockMvc.perform(get("/api/v1/reports/" + id).header("Authorization", forged))
                .andExpect(status().isUnauthorized());
    }

    @Test
    public void healthStaysPublic() throws Exception {
        mockMvc.perform(get("/health")).andExpect(status().isOk());
    }

    // ---- per-report ownership ----

    @Test
    public void otherUsersReportCannotBeReadOrDownloaded() throws Exception {
        Long id = completedReportOwnedBy(OWNER);

        mockMvc.perform(get("/api/v1/reports/" + id)
                        .header("Authorization", TestTokens.bearer(ATTACKER)))
                .andExpect(status().isNotFound());
        mockMvc.perform(get("/api/v1/reports/" + id + "/download")
                        .header("Authorization", TestTokens.bearer(ATTACKER)))
                .andExpect(status().isNotFound());

        mockMvc.perform(get("/api/v1/reports/" + id)
                        .header("Authorization", TestTokens.bearer(OWNER)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.requestedBy", is(OWNER)));
        mockMvc.perform(get("/api/v1/reports/" + id + "/download")
                        .header("Authorization", TestTokens.bearer(OWNER)))
                .andExpect(status().isOk())
                .andExpect(content().string("owner's report contents"));
    }

    @Test
    public void otherUsersReportCannotBeDeleted() throws Exception {
        Long id = completedReportOwnedBy(OWNER);

        mockMvc.perform(delete("/api/v1/reports/" + id)
                        .header("Authorization", TestTokens.bearer(ATTACKER)))
                .andExpect(status().isNotFound());
        assertTrue(reportRepository.findById(id).isPresent());

        mockMvc.perform(delete("/api/v1/reports/" + id)
                        .header("Authorization", TestTokens.bearer(OWNER)))
                .andExpect(status().isNoContent());
        assertTrue(!reportRepository.findById(id).isPresent());
    }

    @Test
    public void listingAnotherUsersReportsIsForbidden() throws Exception {
        completedReportOwnedBy(OWNER);

        mockMvc.perform(get("/api/v1/reports").param("userId", OWNER)
                        .header("Authorization", TestTokens.bearer(ATTACKER)))
                .andExpect(status().isForbidden());
    }

    @Test
    public void listingByStatusOnlyReturnsCallersOwnReports() throws Exception {
        completedReportOwnedBy(OWNER);
        completedReportOwnedBy(ATTACKER);

        mockMvc.perform(get("/api/v1/reports").param("status", "COMPLETED")
                        .header("Authorization", TestTokens.bearer(ATTACKER)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.reports[*].requestedBy", everyItem(is(ATTACKER))));
        mockMvc.perform(get("/api/v1/reports")
                        .header("Authorization", TestTokens.bearer(ATTACKER)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.reports[*].requestedBy", everyItem(is(ATTACKER))));
    }

    @Test
    public void requestedByInBodyIsIgnoredOwnershipComesFromToken() throws Exception {
        ReportRequest request = buildRequest("Spoofed Owner");
        request.setRequestedBy(OWNER);

        mockMvc.perform(post("/api/v1/reports")
                        .header("Authorization", TestTokens.bearer(ATTACKER))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isAccepted())
                .andExpect(jsonPath("$.requestedBy", is(ATTACKER)));
    }

    // ---- admin ----

    @Test
    public void adminCanReadListAndDeleteAnyReport() throws Exception {
        Long id = completedReportOwnedBy(OWNER);
        String admin = TestTokens.bearer(ADMIN, "ADMIN");

        mockMvc.perform(get("/api/v1/reports/" + id).header("Authorization", admin))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.requestedBy", is(OWNER)));
        mockMvc.perform(get("/api/v1/reports").param("userId", OWNER).header("Authorization", admin))
                .andExpect(status().isOk());
        mockMvc.perform(delete("/api/v1/reports/" + id).header("Authorization", admin))
                .andExpect(status().isNoContent());
    }

    @Test
    public void archiveAndReconciliationRequireAdminRole() throws Exception {
        String user = TestTokens.bearer(OWNER);
        String admin = TestTokens.bearer(ADMIN, "ADMIN");
        String[] paths = {
            "/api/v1/reports/reconciliation",
            "/api/reports/reconciliation",
            "/api/archive/documents/doc-1",
            "/api/v1/archive/documents/doc-1",
            "/api/v1/reports/archive/documents/doc-1",
        };
        for (String path : paths) {
            mockMvc.perform(get(path).header("Authorization", user))
                    .andExpect(status().isForbidden());
            int adminStatus = mockMvc.perform(get(path).header("Authorization", admin))
                    .andReturn().getResponse().getStatus();
            assertNotEquals(path + " should not be unauthorized for admins", 401, adminStatus);
            assertNotEquals(path + " should not be forbidden for admins", 403, adminStatus);
        }
    }

    // ---- helpers ----

    private ReportRequest buildRequest(String name) {
        ReportRequest request = new ReportRequest();
        request.setReportName(name);
        request.setCategory(ReportCategory.AUDIT_LOG);
        request.setReportType(ReportType.CSV);
        request.setDateFrom(new Date(System.currentTimeMillis() - 86400000L * 7));
        request.setDateTo(new Date());
        return request;
    }

    /** Persists a COMPLETED report with a real file on disk, as the generation worker would. */
    private Long completedReportOwnedBy(String userId) throws Exception {
        File file = Files.createTempFile("ownership-test-", ".csv").toFile();
        file.deleteOnExit();
        Files.write(file.toPath(), "owner's report contents".getBytes(StandardCharsets.UTF_8));

        Report report = new Report();
        report.setReportName("Report of " + userId);
        report.setCategory(ReportCategory.AUDIT_LOG);
        report.setReportType(ReportType.CSV);
        report.setRequestedBy(userId);
        report.setStatus(ReportStatus.COMPLETED);
        report.setCreatedAt(new Date());
        report.setCompletedAt(new Date());
        report.setFilePath(file.getAbsolutePath());
        return reportRepository.save(report).getId();
    }
}
