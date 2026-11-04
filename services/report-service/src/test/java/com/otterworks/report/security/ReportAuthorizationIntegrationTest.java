package com.otterworks.report.security;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.otterworks.report.model.ReportCategory;
import com.otterworks.report.model.ReportRequest;
import com.otterworks.report.model.ReportType;
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

import java.util.UUID;

import static org.hamcrest.Matchers.everyItem;
import static org.hamcrest.Matchers.hasItem;
import static org.hamcrest.Matchers.is;
import static org.hamcrest.Matchers.not;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * Caller identity and object-level authorization on /api/v1/reports/**.
 */
@RunWith(SpringRunner.class)
@SpringBootTest(properties = {
        "otterworks.security.jwt-secret=" + TestTokens.SECRET,
        "otterworks.security.jwt-peer-secret=" + TestTokens.PEER_SECRET
})
@AutoConfigureMockMvc
@ActiveProfiles("test")
public class ReportAuthorizationIntegrationTest {

    private static final String AUTH = "Authorization";

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    private final String alice = "alice-" + UUID.randomUUID();
    private final String mallory = "mallory-" + UUID.randomUUID();

    @Test
    public void requestsWithoutTokenAreRejected() throws Exception {
        mockMvc.perform(get("/api/v1/reports")).andExpect(status().isUnauthorized());
        mockMvc.perform(get("/api/v1/reports/1")).andExpect(status().isUnauthorized());
        mockMvc.perform(get("/api/v1/reports/1/download")).andExpect(status().isUnauthorized());
        mockMvc.perform(delete("/api/v1/reports/1")).andExpect(status().isUnauthorized());
        mockMvc.perform(post("/api/v1/reports")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body("No Token", ReportCategory.USAGE_ANALYTICS, alice)))
                .andExpect(status().isUnauthorized());
    }

    @Test
    public void gatewayHeaderAloneIsNotTrusted() throws Exception {
        mockMvc.perform(get("/api/v1/reports").header("X-User-ID", alice))
                .andExpect(status().isUnauthorized());
    }

    @Test
    public void tokenSignedWithAnotherKeyIsRejected() throws Exception {
        String forged = TestTokens.token("not-the-report-service-secret-0123456789abcdef", alice, "access");
        mockMvc.perform(get("/api/v1/reports").header(AUTH, "Bearer " + forged))
                .andExpect(status().isUnauthorized());
    }

    @Test
    public void refreshTokenIsRejected() throws Exception {
        String refresh = TestTokens.token(TestTokens.SECRET, alice, "refresh");
        mockMvc.perform(get("/api/v1/reports").header(AUTH, "Bearer " + refresh))
                .andExpect(status().isUnauthorized());
    }

    @Test
    public void tokenWithoutAccessTypeIsRejected() throws Exception {
        String untyped = TestTokens.token(TestTokens.SECRET, alice, null);
        mockMvc.perform(get("/api/v1/reports").header(AUTH, "Bearer " + untyped))
                .andExpect(status().isUnauthorized());
    }

    @Test
    public void legacyReconciliationAliasKeepsItsAccessRule() throws Exception {
        mockMvc.perform(get("/api/v1/reports/reconciliation"))
                .andExpect(status().is(not(401)));
    }

    @Test
    public void gatewayHeaderMustMatchTokenSubject() throws Exception {
        mockMvc.perform(get("/api/v1/reports")
                        .header(AUTH, TestTokens.bearer(mallory))
                        .header("X-User-ID", alice))
                .andExpect(status().isUnauthorized());
        mockMvc.perform(get("/api/v1/reports")
                        .header(AUTH, TestTokens.bearer(alice))
                        .header("X-User-ID", alice))
                .andExpect(status().isOk());
    }

    @Test
    public void peerSecretTokenIsAccepted() throws Exception {
        String peer = TestTokens.token(TestTokens.PEER_SECRET, alice, "access");
        mockMvc.perform(get("/api/v1/reports").header(AUTH, "Bearer " + peer))
                .andExpect(status().isOk());
    }

    @Test
    public void requesterComesFromTokenNotBody() throws Exception {
        mockMvc.perform(post("/api/v1/reports")
                        .header(AUTH, TestTokens.bearer(mallory))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body("Spoofed Requester", ReportCategory.USAGE_ANALYTICS, alice)))
                .andExpect(status().isAccepted())
                .andExpect(jsonPath("$.requestedBy", is(mallory)));

        mockMvc.perform(get("/api/v1/reports").param("userId", alice)
                        .header(AUTH, TestTokens.bearer(alice)))
                .andExpect(jsonPath("$.total", is(0)));
    }

    @Test
    public void requestedByMayBeOmitted() throws Exception {
        mockMvc.perform(post("/api/v1/reports")
                        .header(AUTH, TestTokens.bearer(alice))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body("No Requester", ReportCategory.USAGE_ANALYTICS, null)))
                .andExpect(status().isAccepted())
                .andExpect(jsonPath("$.requestedBy", is(alice)));
    }

    @Test
    public void callerOnlyListsOwnReports() throws Exception {
        Long aliceReport = create(alice, "Alice Usage", ReportCategory.USAGE_ANALYTICS);
        Long malloryReport = create(mallory, "Mallory Usage", ReportCategory.USAGE_ANALYTICS);

        mockMvc.perform(get("/api/v1/reports").param("userId", alice)
                        .header(AUTH, TestTokens.bearer(alice)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.reports[*].id", hasItem(aliceReport.intValue())))
                .andExpect(jsonPath("$.reports[*].id", not(hasItem(malloryReport.intValue()))))
                .andExpect(jsonPath("$.reports[*].requestedBy", everyItem(is(alice))));

        mockMvc.perform(get("/api/v1/reports").param("userId", alice)
                        .header(AUTH, TestTokens.bearer(mallory)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.total", is(0)));

        for (String status : new String[] {"PENDING", "GENERATING", "COMPLETED", "FAILED"}) {
            mockMvc.perform(get("/api/v1/reports").param("status", status)
                            .header(AUTH, TestTokens.bearer(mallory)))
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$.reports[*].id", not(hasItem(aliceReport.intValue()))))
                    .andExpect(jsonPath("$.reports[*].requestedBy", everyItem(is(mallory))));
        }
        mockMvc.perform(get("/api/v1/reports").header(AUTH, TestTokens.bearer(mallory)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.reports[*].requestedBy", everyItem(is(mallory))));
    }

    @Test
    public void otherUsersReportIsNotFound() throws Exception {
        Long id = create(alice, "Alice Private", ReportCategory.STORAGE_SUMMARY);

        mockMvc.perform(get("/api/v1/reports/" + id).header(AUTH, TestTokens.bearer(mallory)))
                .andExpect(status().isNotFound());
        mockMvc.perform(get("/api/v1/reports/" + id + "/download").header(AUTH, TestTokens.bearer(mallory)))
                .andExpect(status().isNotFound());
        mockMvc.perform(delete("/api/v1/reports/" + id).header(AUTH, TestTokens.bearer(mallory)))
                .andExpect(status().isNotFound());

        mockMvc.perform(get("/api/v1/reports/" + id).header(AUTH, TestTokens.bearer(alice)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.requestedBy", is(alice)));
        mockMvc.perform(delete("/api/v1/reports/" + id).header(AUTH, TestTokens.bearer(alice)))
                .andExpect(status().isNoContent());
    }

    @Test
    public void adminRoleDoesNotGrantAccessToOtherUsersReports() throws Exception {
        Long id = create(alice, "Alice Usage For Admin", ReportCategory.USAGE_ANALYTICS);
        mockMvc.perform(get("/api/v1/reports/" + id).header(AUTH, TestTokens.bearer(mallory, "ADMIN")))
                .andExpect(status().isNotFound());
    }

    @Test
    public void auditAndComplianceReportsRequireAdmin() throws Exception {
        for (ReportCategory category : new ReportCategory[] {ReportCategory.AUDIT_LOG, ReportCategory.COMPLIANCE}) {
            mockMvc.perform(post("/api/v1/reports")
                            .header(AUTH, TestTokens.bearer(mallory, "USER", "EDITOR", "OWNER"))
                            .contentType(MediaType.APPLICATION_JSON)
                            .content(body("Restricted " + category, category, mallory)))
                    .andExpect(status().isForbidden());

            mockMvc.perform(post("/api/v1/reports")
                            .header(AUTH, TestTokens.bearer(alice, "USER", "ADMIN"))
                            .contentType(MediaType.APPLICATION_JSON)
                            .content(body("Admin " + category, category, alice)))
                    .andExpect(status().isAccepted())
                    .andExpect(jsonPath("$.category", is(category.name())));
        }
    }

    @Test
    public void restrictedReportIsHiddenOnceCallerIsNoLongerAdmin() throws Exception {
        Long id = create(alice, "Alice Audit", ReportCategory.AUDIT_LOG, "ADMIN");

        mockMvc.perform(get("/api/v1/reports/" + id).header(AUTH, TestTokens.bearer(alice, "ADMIN")))
                .andExpect(status().isOk());
        mockMvc.perform(get("/api/v1/reports/" + id).header(AUTH, TestTokens.bearer(alice, "USER")))
                .andExpect(status().isNotFound());
        mockMvc.perform(get("/api/v1/reports/" + id + "/download").header(AUTH, TestTokens.bearer(alice, "USER")))
                .andExpect(status().isNotFound());
        mockMvc.perform(get("/api/v1/reports").param("userId", alice).header(AUTH, TestTokens.bearer(alice)))
                .andExpect(jsonPath("$.reports[*].id", not(hasItem(id.intValue()))));
    }

    private Long create(String user, String name, ReportCategory category, String... roles) throws Exception {
        MvcResult result = mockMvc.perform(post("/api/v1/reports")
                        .header(AUTH, TestTokens.bearer(user, roles))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body(name, category, user)))
                .andExpect(status().isAccepted())
                .andReturn();
        return objectMapper.readTree(result.getResponse().getContentAsString()).get("id").asLong();
    }

    private String body(String name, ReportCategory category, String requestedBy) throws Exception {
        ReportRequest request = new ReportRequest();
        request.setReportName(name);
        request.setCategory(category);
        request.setReportType(ReportType.CSV);
        request.setRequestedBy(requestedBy);
        return objectMapper.writeValueAsString(request);
    }
}
