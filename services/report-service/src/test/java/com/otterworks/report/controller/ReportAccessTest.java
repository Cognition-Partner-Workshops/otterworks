package com.otterworks.report.controller;

import com.otterworks.report.config.SecurityConfig;
import com.otterworks.report.model.Report;
import com.otterworks.report.model.ReportCategory;
import com.otterworks.report.model.ReportRequest;
import com.otterworks.report.model.ReportStatus;
import com.otterworks.report.model.ReportType;
import com.otterworks.report.service.ReportService;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.Base64;
import java.util.Optional;
import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.context.annotation.Import;
import org.springframework.http.MediaType;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.context.junit4.SpringRunner;
import org.springframework.test.web.servlet.MockMvc;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@RunWith(SpringRunner.class)
@WebMvcTest(ReportController.class)
@Import(SecurityConfig.class)
@TestPropertySource(properties = "JWT_SECRET=report-access-test-secret-at-least-32-bytes-long")
public class ReportAccessTest {
    @Autowired
    private MockMvc mvc;
    @MockBean
    private ReportService service;
    private Report owned;

    public static String token(String user, String role) throws Exception {
        String payload = "{\"sub\":\"" + user + "\",\"roles\":[\"" + role
                + "\"],\"type\":\"access\",\"exp\":4102444800}";
        Base64.Encoder encoder = Base64.getUrlEncoder().withoutPadding();
        String input = encoder.encodeToString("{\"alg\":\"HS256\"}".getBytes(StandardCharsets.UTF_8))
                + "." + encoder.encodeToString(payload.getBytes(StandardCharsets.UTF_8));
        Mac mac = Mac.getInstance("HmacSHA256");
        mac.init(new SecretKeySpec("report-access-test-secret-at-least-32-bytes-long"
                .getBytes(StandardCharsets.UTF_8), "HmacSHA256"));
        return "Bearer " + input + "." + encoder.encodeToString(mac.doFinal(input.getBytes(StandardCharsets.UTF_8)));
    }

    @Before
    public void setup() {
        owned = new Report();
        owned.setId(1L);
        owned.setRequestedBy("owner");
        owned.setReportName("private");
        owned.setCategory(ReportCategory.STORAGE_SUMMARY);
        owned.setReportType(ReportType.CSV);
        owned.setStatus(ReportStatus.PENDING);
        when(service.getReport(1L)).thenReturn(Optional.of(owned));
        when(service.deleteReport(1L)).thenReturn(true);
        when(service.getReportsByUser("caller")).thenReturn(Arrays.asList());
        when(service.createReport(any(ReportRequest.class))).thenAnswer(invocation -> {
            ReportRequest request = invocation.getArgument(0);
            owned.setRequestedBy(request.getRequestedBy());
            return owned;
        });
    }

    @Test
    public void anonymousAndSpoofedIdentityAreRejected() throws Exception {
        mvc.perform(get("/api/v1/reports").header("X-User-ID", "owner"))
                .andExpect(status().isUnauthorized());
        mvc.perform(get("/api/v1/reports").header("Authorization", "Bearer not-a-token"))
                .andExpect(status().isUnauthorized());
    }

    @Test
    public void sensitiveReportsRemainPrivilegedEvenForTheirOwner() throws Exception {
        for (ReportCategory category : Arrays.asList(ReportCategory.AUDIT_LOG,
                ReportCategory.COMPLIANCE, ReportCategory.USER_ACTIVITY)) {
            owned.setCategory(category);
            when(service.getReportsByUser("owner")).thenReturn(Arrays.asList(owned));
            mvc.perform(get("/api/v1/reports/1").header("Authorization", token("owner", "USER")))
                    .andExpect(status().isNotFound());
            mvc.perform(get("/api/v1/reports/1/download").header("Authorization", token("owner", "USER")))
                    .andExpect(status().isNotFound());
            mvc.perform(get("/api/v1/reports").header("Authorization", token("owner", "USER")))
                    .andExpect(jsonPath("$.total").value(0));
            mvc.perform(get("/api/v1/reports/1").header("Authorization", token("owner", "AUDITOR")))
                    .andExpect(status().isOk());
        }
    }

    @Test
    public void nonOwnerCannotReadDownloadOrDelete() throws Exception {
        String auth = token("caller", "USER");
        mvc.perform(get("/api/v1/reports/1").header("Authorization", auth)).andExpect(status().isNotFound());
        mvc.perform(get("/api/v1/reports/1/download").header("Authorization", auth))
                .andExpect(status().isNotFound());
        mvc.perform(delete("/api/v1/reports/1").header("Authorization", auth)).andExpect(status().isNotFound());
        verify(service, never()).deleteReport(1L);
    }

    @Test
    public void ownerCanReadAndDelete() throws Exception {
        String auth = token("owner", "USER");
        mvc.perform(get("/api/v1/reports/1").header("Authorization", auth)).andExpect(status().isOk());
        mvc.perform(delete("/api/v1/reports/1").header("Authorization", auth)).andExpect(status().isNoContent());
    }

    @Test
    public void listIgnoresAnotherUsersQuery() throws Exception {
        mvc.perform(get("/api/v1/reports?userId=owner").header("Authorization", token("caller", "USER")))
                .andExpect(status().isOk()).andExpect(jsonPath("$.total").value(0));
        verify(service).getReportsByUser("caller");
        verify(service, never()).getReportsByUser("owner");
    }

    @Test
    public void createUsesAuthenticatedRequester() throws Exception {
        mvc.perform(post("/api/v1/reports").header("Authorization", token("caller", "USER"))
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"reportName\":\"test\",\"category\":\"STORAGE_SUMMARY\","
                        + "\"reportType\":\"CSV\",\"requestedBy\":\"owner\"}"))
                .andExpect(status().isAccepted()).andExpect(jsonPath("$.requestedBy").value("caller"));
    }

    @Test
    public void normalUserCannotRequestSensitiveReports() throws Exception {
        for (String category : Arrays.asList("AUDIT_LOG", "COMPLIANCE", "USER_ACTIVITY")) {
            mvc.perform(post("/api/v1/reports").header("Authorization", token("caller", "USER"))
                    .contentType(MediaType.APPLICATION_JSON)
                    .content("{\"reportName\":\"test\",\"category\":\"" + category
                            + "\",\"reportType\":\"CSV\",\"requestedBy\":\"caller\"}"))
                    .andExpect(status().isForbidden());
        }
        verify(service, never()).createReport(any(ReportRequest.class));
    }

    @Test
    public void auditorCanRequestAuditReports() throws Exception {
        mvc.perform(post("/api/v1/reports").header("Authorization", token("caller", "AUDITOR"))
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"reportName\":\"test\",\"category\":\"AUDIT_LOG\",\"reportType\":\"CSV\"}"))
                .andExpect(status().isAccepted());
    }
}
