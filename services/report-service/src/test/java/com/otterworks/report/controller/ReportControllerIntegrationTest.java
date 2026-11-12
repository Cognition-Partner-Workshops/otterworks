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
import org.springframework.test.web.servlet.request.MockHttpServletRequestBuilder;

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

    private static final String OWNER = "report-owner";
    private static final String INTRUDER = "report-intruder";
    private static final String ADMIN = "report-admin";

    // ---- POST /api/v1/reports ----

    @Test
    public void createPdfReportReturns202WithCorrectBody() throws Exception {
        ReportRequest request = buildRequest("Integration PDF Report",
                ReportCategory.USAGE_ANALYTICS, ReportType.PDF, "integration-user-1");

        mockMvc.perform(asUser(post("/api/v1/reports"), request.getRequestedBy())
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

        mockMvc.perform(asUser(post("/api/v1/reports"), request.getRequestedBy())
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

        mockMvc.perform(asUser(post("/api/v1/reports"), request.getRequestedBy())
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

        mockMvc.perform(asUser(post("/api/v1/reports"), request.getRequestedBy())
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

        mockMvc.perform(asUser(post("/api/v1/reports"), request.getRequestedBy())
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

        mockMvc.perform(asUser(post("/api/v1/reports"), request.getRequestedBy())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isBadRequest());
    }

    // ---- GET /api/v1/reports/{id} ----

    @Test
    public void getReportByIdReturnsCreatedReport() throws Exception {
        Long id = createReportAndReturnId("Fetch By Id Report",
                ReportCategory.SYSTEM_HEALTH, ReportType.PDF, "integration-user-7");

        mockMvc.perform(asUser(get("/api/v1/reports/" + id), "integration-user-7"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.id", is(id.intValue())))
                .andExpect(jsonPath("$.reportName", is("Fetch By Id Report")))
                .andExpect(jsonPath("$.category", is("SYSTEM_HEALTH")));
    }

    @Test
    public void getNonExistentReportReturns404() throws Exception {
        mockMvc.perform(asUser(get("/api/v1/reports/999999"), "integration-user-7"))
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

        mockMvc.perform(asUser(get("/api/v1/reports"), userId).param("userId", userId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.reports").isArray())
                .andExpect(jsonPath("$.total").isNumber());
    }

    @Test
    public void listReportsForUnknownUserReturnsEmptyArray() throws Exception {
        mockMvc.perform(asUser(get("/api/v1/reports"), ADMIN, "ADMIN")
                        .param("userId", "nonexistent-user-xyz"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.reports").isArray())
                .andExpect(jsonPath("$.total", is(0)));
    }

    @Test
    public void listReportsByStatusReturnsArray() throws Exception {
        mockMvc.perform(asUser(get("/api/v1/reports"), "integration-user-7").param("status", "COMPLETED"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.reports").isArray());
    }

    // ---- GET /api/v1/reports/{id}/download ----

    @Test
    public void downloadNonExistentReportReturns404() throws Exception {
        mockMvc.perform(asUser(get("/api/v1/reports/999999/download"), "integration-user-8"))
                .andExpect(status().isNotFound());
    }

    @Test
    public void downloadPendingReportReturns409() throws Exception {
        Long id = createReportAndReturnId("Download Pending Report",
                ReportCategory.USAGE_ANALYTICS, ReportType.PDF, "integration-user-8");

        MvcResult download = mockMvc.perform(asUser(get("/api/v1/reports/" + id + "/download"), "integration-user-8"))
                .andReturn();

        // Status is read after the download so it cannot go stale in the wrong direction:
        // generation only moves forward, so a report still pending here was pending during
        // the download too.
        MvcResult result = mockMvc.perform(asUser(get("/api/v1/reports/" + id), "integration-user-8"))
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

        mockMvc.perform(asUser(delete("/api/v1/reports/" + id), "integration-user-9"))
                .andExpect(status().isNoContent());

        mockMvc.perform(asUser(get("/api/v1/reports/" + id), "integration-user-9"))
                .andExpect(status().isNotFound());
    }

    @Test
    public void deleteNonExistentReportReturns404() throws Exception {
        mockMvc.perform(asUser(delete("/api/v1/reports/999999"), "integration-user-9"))
                .andExpect(status().isNotFound());
    }

    // ---- Ownership / authorization ----

    @Test
    public void requestWithoutCallerIdentityReturns401() throws Exception {
        Long id = createReportAndReturnId("Anonymous Probe Report",
                ReportCategory.AUDIT_LOG, ReportType.CSV, OWNER);

        mockMvc.perform(get("/api/v1/reports/" + id))
                .andExpect(status().isUnauthorized());
        mockMvc.perform(get("/api/v1/reports"))
                .andExpect(status().isUnauthorized());
        mockMvc.perform(delete("/api/v1/reports/" + id))
                .andExpect(status().isUnauthorized());
    }

    @Test
    public void otherUserGets404ForSomeoneElsesReport() throws Exception {
        Long id = createReportAndReturnId("Owner Only Report",
                ReportCategory.AUDIT_LOG, ReportType.CSV, OWNER);

        mockMvc.perform(asUser(get("/api/v1/reports/" + id), INTRUDER))
                .andExpect(status().isNotFound());
        mockMvc.perform(asUser(get("/api/v1/reports/" + id + "/download"), INTRUDER))
                .andExpect(status().isNotFound());
        mockMvc.perform(asUser(delete("/api/v1/reports/" + id), INTRUDER))
                .andExpect(status().isNotFound());

        mockMvc.perform(asUser(get("/api/v1/reports/" + id), OWNER))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.requestedBy", is(OWNER)));
    }

    @Test
    public void unfilteredListContainsOnlyCallersReports() throws Exception {
        String owner = "list-owner-" + System.nanoTime();
        String other = "list-other-" + System.nanoTime();
        createReportAndReturnId("Mine", ReportCategory.AUDIT_LOG, ReportType.CSV, owner);
        createReportAndReturnId("Theirs", ReportCategory.AUDIT_LOG, ReportType.CSV, other);

        mockMvc.perform(asUser(get("/api/v1/reports"), owner))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.total", is(1)))
                .andExpect(jsonPath("$.reports[0].requestedBy", is(owner)));
    }

    @Test
    public void userIdFilterForAnotherUserReturnsNothingForNonAdmin() throws Exception {
        String owner = "filter-owner-" + System.nanoTime();
        createReportAndReturnId("Filtered", ReportCategory.AUDIT_LOG, ReportType.CSV, owner);

        mockMvc.perform(asUser(get("/api/v1/reports"), INTRUDER).param("userId", owner))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.total", is(0)));
        mockMvc.perform(asUser(get("/api/v1/reports"), ADMIN, "ADMIN").param("userId", owner))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.total", is(1)));
    }

    @Test
    public void createIgnoresRequestedByAndUsesCaller() throws Exception {
        ReportRequest request = buildRequest("Spoofed Owner Report",
                ReportCategory.AUDIT_LOG, ReportType.CSV, OWNER);

        mockMvc.perform(asUser(post("/api/v1/reports"), INTRUDER)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isAccepted())
                .andExpect(jsonPath("$.requestedBy", is(INTRUDER)));
    }

    @Test
    public void adminCanReadAnyReport() throws Exception {
        Long id = createReportAndReturnId("Admin Visible Report",
                ReportCategory.AUDIT_LOG, ReportType.CSV, OWNER);

        mockMvc.perform(asUser(get("/api/v1/reports/" + id), ADMIN, "USER,ADMIN"))
                .andExpect(status().isOk());
    }

    @Test
    public void archiveRoutesRequireAdmin() throws Exception {
        for (String path : new String[] {
                "/api/v1/reports/archive/documents/DOC-1",
                "/api/v1/archive/documents/DOC-1",
                "/api/archive/documents/DOC-1/hash"}) {
            mockMvc.perform(get(path))
                    .andExpect(status().isUnauthorized());
            mockMvc.perform(asUser(get(path), INTRUDER))
                    .andExpect(status().isForbidden());
            mockMvc.perform(asUser(get(path), ADMIN, "ADMIN"))
                    .andExpect(status().isNotFound());
        }
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

    private static MockHttpServletRequestBuilder asUser(MockHttpServletRequestBuilder builder,
                                                        String userId) {
        return builder.header("X-User-ID", userId);
    }

    private static MockHttpServletRequestBuilder asUser(MockHttpServletRequestBuilder builder,
                                                        String userId, String roles) {
        return builder.header("X-User-ID", userId).header("X-User-Roles", roles);
    }

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
        MvcResult result = mockMvc.perform(asUser(post("/api/v1/reports"), request.getRequestedBy())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isAccepted())
                .andReturn();

        String body = result.getResponse().getContentAsString();
        return objectMapper.readTree(body).get("id").asLong();
    }
}
