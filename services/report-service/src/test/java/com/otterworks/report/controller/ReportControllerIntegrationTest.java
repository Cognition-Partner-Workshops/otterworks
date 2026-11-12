package com.otterworks.report.controller;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.otterworks.report.model.ReportCategory;
import com.otterworks.report.model.ReportRequest;
import com.otterworks.report.model.ReportType;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.junit4.SpringRunner;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;

import java.util.Date;

import static org.junit.Assert.assertEquals;
import static org.hamcrest.Matchers.anyOf;
import static org.hamcrest.Matchers.is;
import static org.hamcrest.Matchers.notNullValue;
import static org.hamcrest.Matchers.nullValue;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * Integration tests for {@link ReportController} REST endpoints.
 *
 * Verifies HTTP status codes, content types, and response body structure
 * for every controller action. Uses a real Spring context with an H2
 * in-memory database (profile "test").
 *
 * Written in JUnit 4 style to match the current stack. After the JUnit 5
 * migration (Axis 4), replace:
 *   - @RunWith(SpringRunner.class) -> remove
 *   - org.junit.Test              -> org.junit.jupiter.api.Test
 */
@RunWith(SpringRunner.class)
@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
public class ReportControllerIntegrationTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    /** Identity header set by the API gateway (no JWT secret is configured in tests). */
    private static final String USER_HEADER = "X-User-ID";

    // ---- POST /api/v1/reports ----

    @Test
    public void createPdfReportReturns202WithCorrectBody() throws Exception {
        ReportRequest request = buildRequest("Integration PDF Report",
                ReportCategory.USAGE_ANALYTICS, ReportType.PDF, "integration-user-1");

        mockMvc.perform(post("/api/v1/reports")
                        .header(USER_HEADER, "integration-user-1")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isAccepted())
                .andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_JSON))
                .andExpect(jsonPath("$.id", notNullValue()))
                .andExpect(jsonPath("$.reportName", is("Integration PDF Report")))
                .andExpect(jsonPath("$.category", is("USAGE_ANALYTICS")))
                .andExpect(jsonPath("$.reportType", is("PDF")))
                .andExpect(jsonPath("$.requestedBy", is("integration-user-1")))
                .andExpect(jsonPath("$.status",
                        anyOf(is("PENDING"), is("GENERATING"), is("COMPLETED"))));
    }

    @Test
    public void createCsvReportReturns202() throws Exception {
        ReportRequest request = buildRequest("Integration CSV Report",
                ReportCategory.AUDIT_LOG, ReportType.CSV, "integration-user-2");

        mockMvc.perform(post("/api/v1/reports")
                        .header(USER_HEADER, "integration-user-2")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isAccepted())
                .andExpect(jsonPath("$.reportType", is("CSV")))
                .andExpect(jsonPath("$.category", is("AUDIT_LOG")));
    }

    @Test
    public void createExcelReportReturns202() throws Exception {
        ReportRequest request = buildRequest("Integration Excel Report",
                ReportCategory.STORAGE_SUMMARY, ReportType.EXCEL, "integration-user-3");

        mockMvc.perform(post("/api/v1/reports")
                        .header(USER_HEADER, "integration-user-3")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isAccepted())
                .andExpect(jsonPath("$.reportType", is("EXCEL")))
                .andExpect(jsonPath("$.category", is("STORAGE_SUMMARY")));
    }

    @Test
    public void createReportWithoutNameReturns400() throws Exception {
        ReportRequest request = new ReportRequest();
        request.setCategory(ReportCategory.COMPLIANCE);
        request.setReportType(ReportType.PDF);
        request.setRequestedBy("integration-user-4");

        mockMvc.perform(post("/api/v1/reports")
                        .header(USER_HEADER, "integration-user-4")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isBadRequest());
    }

    @Test
    public void createReportWithoutCategoryReturns400() throws Exception {
        ReportRequest request = new ReportRequest();
        request.setReportName("Missing Category Report");
        request.setReportType(ReportType.CSV);
        request.setRequestedBy("integration-user-5");

        mockMvc.perform(post("/api/v1/reports")
                        .header(USER_HEADER, "integration-user-5")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isBadRequest());
    }

    @Test
    public void createReportWithoutTypeReturns400() throws Exception {
        ReportRequest request = new ReportRequest();
        request.setReportName("Missing Type Report");
        request.setCategory(ReportCategory.USER_ACTIVITY);
        request.setRequestedBy("integration-user-6");

        mockMvc.perform(post("/api/v1/reports")
                        .header(USER_HEADER, "integration-user-6")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isBadRequest());
    }

    // ---- GET /api/v1/reports/{id} ----

    @Test
    public void getReportByIdReturnsCreatedReport() throws Exception {
        Long id = createReportAndReturnId("Fetch By Id Report",
                ReportCategory.SYSTEM_HEALTH, ReportType.PDF, "integration-user-7");

        mockMvc.perform(get("/api/v1/reports/" + id).header(USER_HEADER, "integration-user-7"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.id", is(id.intValue())))
                .andExpect(jsonPath("$.reportName", is("Fetch By Id Report")))
                .andExpect(jsonPath("$.category", is("SYSTEM_HEALTH")));
    }

    @Test
    public void getNonExistentReportReturns404() throws Exception {
        mockMvc.perform(get("/api/v1/reports/999999").header(USER_HEADER, "integration-user-7"))
                .andExpect(status().isNotFound());
    }

    // ---- GET /api/v1/reports ----

    @Test
    public void listReportsByUserIdReturnsArray() throws Exception {
        String userId = "list-test-user-" + System.currentTimeMillis();
        createReportAndReturnId("List Test 1", ReportCategory.AUDIT_LOG,
                ReportType.CSV, userId);
        createReportAndReturnId("List Test 2", ReportCategory.AUDIT_LOG,
                ReportType.PDF, userId);

        mockMvc.perform(get("/api/v1/reports").param("userId", userId).header(USER_HEADER, userId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.reports").isArray())
                .andExpect(jsonPath("$.total").isNumber());
    }

    @Test
    public void listReportsForUnknownUserReturnsEmptyArray() throws Exception {
        mockMvc.perform(get("/api/v1/reports")
                        .header(USER_HEADER, "nonexistent-user-xyz")
                        .param("userId", "nonexistent-user-xyz"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.reports").isArray())
                .andExpect(jsonPath("$.total", is(0)));
    }

    @Test
    public void listReportsByStatusReturnsArray() throws Exception {
        mockMvc.perform(get("/api/v1/reports").param("status", "COMPLETED")
                        .header(USER_HEADER, "integration-user-status"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.reports").isArray());
    }

    // ---- GET /api/v1/reports/{id}/download ----

    @Test
    public void downloadNonExistentReportReturns404() throws Exception {
        mockMvc.perform(get("/api/v1/reports/999999/download").header(USER_HEADER, "integration-user-8"))
                .andExpect(status().isNotFound());
    }

    @Test
    public void downloadPendingReportReturns409() throws Exception {
        Long id = createReportAndReturnId("Download Pending Report",
                ReportCategory.USAGE_ANALYTICS, ReportType.PDF, "integration-user-8");

        MvcResult download = mockMvc.perform(get("/api/v1/reports/" + id + "/download")
                        .header(USER_HEADER, "integration-user-8"))
                .andReturn();

        // Status is read after the download so it cannot go stale in the wrong direction:
        // generation only moves forward, so a report still pending here was pending during
        // the download too.
        MvcResult result = mockMvc.perform(get("/api/v1/reports/" + id).header(USER_HEADER, "integration-user-8"))
                .andReturn();
        String statusVal = objectMapper.readTree(
                result.getResponse().getContentAsString()).get("status").asText();

        if ("PENDING".equals(statusVal) || "GENERATING".equals(statusVal)) {
            assertEquals(HttpStatus.CONFLICT.value(), download.getResponse().getStatus());
        }
    }

    // ---- DELETE /api/v1/reports/{id} ----

    @Test
    public void deleteExistingReportReturns204() throws Exception {
        Long id = createReportAndReturnId("Delete Me Report",
                ReportCategory.COLLABORATION_METRICS, ReportType.CSV, "integration-user-9");

        mockMvc.perform(delete("/api/v1/reports/" + id).header(USER_HEADER, "integration-user-9"))
                .andExpect(status().isNoContent());

        mockMvc.perform(get("/api/v1/reports/" + id).header(USER_HEADER, "integration-user-9"))
                .andExpect(status().isNotFound());
    }

    @Test
    public void deleteNonExistentReportReturns404() throws Exception {
        mockMvc.perform(delete("/api/v1/reports/999999").header(USER_HEADER, "integration-user-9"))
                .andExpect(status().isNotFound());
    }

    // ---- Access control (owner vs. other user; gateway identity header mode) ----

    @Test
    public void unauthenticatedRequestsAreRejectedWith401() throws Exception {
        Long id = createReportAndReturnId("Anonymous Access Report",
                ReportCategory.USAGE_ANALYTICS, ReportType.CSV, "integration-owner-a");

        mockMvc.perform(get("/api/v1/reports/" + id)).andExpect(status().isUnauthorized());
        mockMvc.perform(get("/api/v1/reports")).andExpect(status().isUnauthorized());
        mockMvc.perform(get("/api/v1/reports/" + id + "/download")).andExpect(status().isUnauthorized());
        mockMvc.perform(delete("/api/v1/reports/" + id)).andExpect(status().isUnauthorized());
        mockMvc.perform(post("/api/v1/reports")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(buildRequest("Anon", ReportCategory.AUDIT_LOG,
                                ReportType.CSV, "integration-owner-a"))))
                .andExpect(status().isUnauthorized());
    }

    @Test
    public void otherUserCannotReadDownloadOrDeleteSomeoneElsesReport() throws Exception {
        Long id = createReportAndReturnId("Victim Report",
                ReportCategory.USAGE_ANALYTICS, ReportType.CSV, "integration-owner-a");

        mockMvc.perform(get("/api/v1/reports/" + id).header(USER_HEADER, "integration-attacker-b"))
                .andExpect(status().isForbidden());
        mockMvc.perform(get("/api/v1/reports/" + id + "/download").header(USER_HEADER, "integration-attacker-b"))
                .andExpect(status().isForbidden());
        mockMvc.perform(delete("/api/v1/reports/" + id).header(USER_HEADER, "integration-attacker-b"))
                .andExpect(status().isForbidden());

        // Control: the owner still has full access and the report was not deleted.
        mockMvc.perform(get("/api/v1/reports/" + id).header(USER_HEADER, "integration-owner-a"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.requestedBy", is("integration-owner-a")));
    }

    @Test
    public void otherUserCannotListSomeoneElsesReportsAndListDefaultsToCaller() throws Exception {
        String owner = "integration-owner-list-" + System.currentTimeMillis();
        createReportAndReturnId("Victim List Report", ReportCategory.AUDIT_LOG, ReportType.CSV, owner);

        mockMvc.perform(get("/api/v1/reports").param("userId", owner).header(USER_HEADER, "integration-attacker-b"))
                .andExpect(status().isForbidden());

        // Listing with no filter is scoped to the caller: the attacker never sees the owner's report.
        mockMvc.perform(get("/api/v1/reports").header(USER_HEADER, "integration-attacker-b"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.reports[?(@.requestedBy == '" + owner + "')]").isEmpty());
        mockMvc.perform(get("/api/v1/reports").header(USER_HEADER, owner))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.total", is(1)))
                .andExpect(jsonPath("$.reports[0].requestedBy", is(owner)));
    }

    @Test
    public void createCannotImpersonateAnotherUserAndDefaultsRequesterToCaller() throws Exception {
        mockMvc.perform(post("/api/v1/reports")
                        .header(USER_HEADER, "integration-attacker-b")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(buildRequest("Impersonation", ReportCategory.AUDIT_LOG,
                                ReportType.CSV, "integration-owner-a"))))
                .andExpect(status().isForbidden());

        mockMvc.perform(post("/api/v1/reports")
                        .header(USER_HEADER, "integration-attacker-b")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(buildRequest("Own Report", ReportCategory.AUDIT_LOG,
                                ReportType.CSV, null))))
                .andExpect(status().isAccepted())
                .andExpect(jsonPath("$.requestedBy", is("integration-attacker-b")));
    }

    // ---- Health endpoint ----

    @Test
    public void healthEndpointReturnsServiceMetadata() throws Exception {
        mockMvc.perform(get("/health"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status", is("healthy")))
                .andExpect(jsonPath("$.service", is("report-service")))
                .andExpect(jsonPath("$.version", is("0.1.0")));
    }

    // ---- Helpers ----

    private ReportRequest buildRequest(String name, ReportCategory category,
                                       ReportType type, String requestedBy) {
        ReportRequest request = new ReportRequest();
        request.setReportName(name);
        request.setCategory(category);
        request.setReportType(type);
        request.setRequestedBy(requestedBy);
        request.setDateFrom(new Date(System.currentTimeMillis() - 86400000L * 7));
        request.setDateTo(new Date());
        return request;
    }

    private Long createReportAndReturnId(String name, ReportCategory category,
                                         ReportType type, String requestedBy) throws Exception {
        ReportRequest request = buildRequest(name, category, type, requestedBy);
        MvcResult result = mockMvc.perform(post("/api/v1/reports")
                        .header(USER_HEADER, requestedBy)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isAccepted())
                .andReturn();

        String body = result.getResponse().getContentAsString();
        return objectMapper.readTree(body).get("id").asLong();
    }
}
