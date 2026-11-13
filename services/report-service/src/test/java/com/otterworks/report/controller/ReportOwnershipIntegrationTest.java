package com.otterworks.report.controller;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.otterworks.report.model.Report;
import com.otterworks.report.model.ReportCategory;
import com.otterworks.report.model.ReportRequest;
import com.otterworks.report.model.ReportStatus;
import com.otterworks.report.model.ReportType;
import com.otterworks.report.repository.ReportRepository;
import org.junit.After;
import org.junit.Before;
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
import java.util.UUID;

import static org.hamcrest.Matchers.everyItem;
import static org.hamcrest.Matchers.hasItem;
import static org.hamcrest.Matchers.is;
import static org.hamcrest.Matchers.not;
import static org.junit.Assert.assertTrue;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * Reports are visible only to the user named by the gateway-forwarded X-User-ID header.
 */
@RunWith(SpringRunner.class)
@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
public class ReportOwnershipIntegrationTest {

    private static final String USER_HEADER = "X-User-ID";

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @Autowired
    private ReportRepository reportRepository;

    private String owner;
    private String other;
    private Long ownerReportId;
    private File reportFile;

    @Before
    public void seedCompletedReport() throws Exception {
        owner = "owner-" + UUID.randomUUID();
        other = "other-" + UUID.randomUUID();
        reportFile = File.createTempFile("ownership-report-", ".csv");
        Files.write(reportFile.toPath(), "secret,data\n1,2\n".getBytes(StandardCharsets.UTF_8));

        Report report = new Report();
        report.setReportName("Owner Financials");
        report.setCategory(ReportCategory.AUDIT_LOG);
        report.setReportType(ReportType.CSV);
        report.setStatus(ReportStatus.COMPLETED);
        report.setRequestedBy(owner);
        report.setCreatedAt(new Date());
        report.setCompletedAt(new Date());
        report.setFilePath(reportFile.getAbsolutePath());
        ownerReportId = reportRepository.save(report).getId();
    }

    @After
    public void cleanUp() {
        reportRepository.findById(ownerReportId).ifPresent(reportRepository::delete);
        reportFile.delete();
    }

    @Test
    public void ownerCanReadAndDownloadOwnReport() throws Exception {
        mockMvc.perform(get("/api/v1/reports/" + ownerReportId).header(USER_HEADER, owner))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.requestedBy", is(owner)));

        mockMvc.perform(get("/api/v1/reports/" + ownerReportId + "/download").header(USER_HEADER, owner))
                .andExpect(status().isOk())
                .andExpect(content().string("secret,data\n1,2\n"));
    }

    @Test
    public void otherUserGetsNotFoundOnGet() throws Exception {
        mockMvc.perform(get("/api/v1/reports/" + ownerReportId).header(USER_HEADER, other))
                .andExpect(status().isNotFound());
    }

    @Test
    public void otherUserGetsNotFoundOnDownload() throws Exception {
        mockMvc.perform(get("/api/v1/reports/" + ownerReportId + "/download").header(USER_HEADER, other))
                .andExpect(status().isNotFound());
    }

    @Test
    public void otherUserCannotDeleteReport() throws Exception {
        mockMvc.perform(delete("/api/v1/reports/" + ownerReportId).header(USER_HEADER, other))
                .andExpect(status().isNotFound());

        assertTrue(reportRepository.findById(ownerReportId).isPresent());
        assertTrue(reportFile.exists());
    }

    @Test
    public void unfilteredListOnlyShowsCallerReports() throws Exception {
        mockMvc.perform(get("/api/v1/reports").header(USER_HEADER, other))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.reports[*].id", not(hasItem(ownerReportId.intValue()))))
                .andExpect(jsonPath("$.total", is(0)));

        mockMvc.perform(get("/api/v1/reports").header(USER_HEADER, owner))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.reports[*].id", hasItem(ownerReportId.intValue())))
                .andExpect(jsonPath("$.reports[*].requestedBy", everyItem(is(owner))));
    }

    @Test
    public void statusFilteredListOnlyShowsCallerReports() throws Exception {
        mockMvc.perform(get("/api/v1/reports").param("status", "COMPLETED").header(USER_HEADER, other))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.total", is(0)));
    }

    @Test
    public void listingAnotherUsersReportsIsForbidden() throws Exception {
        mockMvc.perform(get("/api/v1/reports").param("userId", owner).header(USER_HEADER, other))
                .andExpect(status().isForbidden());
    }

    @Test
    public void requestsWithoutCallerIdentityAreRejected() throws Exception {
        mockMvc.perform(get("/api/v1/reports"))
                .andExpect(status().isUnauthorized());
        mockMvc.perform(get("/api/v1/reports/" + ownerReportId))
                .andExpect(status().isUnauthorized());
        mockMvc.perform(get("/api/v1/reports/" + ownerReportId + "/download"))
                .andExpect(status().isUnauthorized());
        mockMvc.perform(delete("/api/v1/reports/" + ownerReportId))
                .andExpect(status().isUnauthorized());
        mockMvc.perform(post("/api/v1/reports")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request(owner))))
                .andExpect(status().isUnauthorized());
        assertTrue(reportRepository.findById(ownerReportId).isPresent());
    }

    @Test
    public void createdReportIsOwnedByCallerNotBodyRequestedBy() throws Exception {
        mockMvc.perform(post("/api/v1/reports")
                        .header(USER_HEADER, other)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request(owner))))
                .andExpect(status().isAccepted())
                .andExpect(jsonPath("$.requestedBy", is(other)));
    }

    private ReportRequest request(String requestedBy) {
        ReportRequest request = new ReportRequest();
        request.setReportName("Spoofed Owner Report");
        request.setCategory(ReportCategory.AUDIT_LOG);
        request.setReportType(ReportType.CSV);
        request.setRequestedBy(requestedBy);
        return request;
    }
}
