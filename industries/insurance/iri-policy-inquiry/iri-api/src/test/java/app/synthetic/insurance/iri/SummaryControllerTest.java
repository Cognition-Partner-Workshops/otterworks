package app.synthetic.insurance.iri;

import java.time.LocalDate;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.dao.DataAccessResourceFailureException;
import org.springframework.test.web.servlet.MockMvc;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest
@AutoConfigureMockMvc
class SummaryControllerTest {
    private static final Map<String, Object> ROW = Map.of("STATUS_CODE", "LP", "PRODUCT_NAME", "Steady Income Annuity",
            "PLAN_CODE", "FLEX", "QUALIFICATION_CODE", "ROTH", "ISSUE_STATE", "AZ", "CURRENCY_CODE", "USD",
            "EFFECTIVE_DATE", java.sql.Timestamp.valueOf(LocalDate.of(2015, 1, 25).atStartOfDay()));

    @Autowired
    private MockMvc mvc;

    @MockBean
    private SummaryRepository repository;

    private String body(String path, String correlationId, int status) throws Exception {
        var request = get(path);
        if (correlationId != null) {
            request = request.header("correlationId", correlationId);
        }
        var response = mvc.perform(request).andExpect(status().is(status)).andReturn().getResponse();
        String id = response.getHeader("correlationId");
        if (correlationId != null) {
            assertEquals(correlationId, id);
        } else {
            assertDoesNotThrow(() -> UUID.fromString(id));
        }
        return response.getContentAsString();
    }

    @Test
    void returnsSchemaValidSummary() throws Exception {
        when(repository.find(1200137L)).thenReturn(Optional.of(ROW));
        String body = body("/v1/policies/1200137/summary", "summary-ok", 200);
        SchemaAssertions.assertValid("PolicySummary", body);
        mvc.perform(get("/v1/policies/1200137/summary"))
                .andExpect(jsonPath("$.policyStatus").value("LAPSED"))
                .andExpect(jsonPath("$.product.planName").value("Steady Income Annuity"))
                .andExpect(jsonPath("$.product.productType").value("DEFERRED"))
                .andExpect(jsonPath("$.product.planCode").value("FLEX"))
                .andExpect(jsonPath("$.qualificationType").value("Roth IRA"))
                .andExpect(jsonPath("$.effectiveDate").value("2015-01-25"))
                .andExpect(jsonPath("$.carrierId").value("SYNANN"))
                .andExpect(jsonPath("$.issueType").value("GUARANTEED"))
                .andExpect(jsonPath("$.policyNumber").doesNotExist());
        assertFalse(body.contains("1200137"));
    }

    @Test
    void canonicalizesZeroPaddedPolicyNumberAndIgnoresFirm() throws Exception {
        when(repository.find(1200137L)).thenReturn(Optional.of(ROW));
        SchemaAssertions.assertValid("PolicySummary", body("/v1/policies/0001200137/summary", null, 200));
        SchemaAssertions.assertValid("PolicySummary", body("/v1/policies/1200137/summary?associatedFirmId=F1", null, 200));
        verify(repository, times(2)).find(1200137L);
    }

    @Test
    void errorsAreSchemaValid() throws Exception {
        when(repository.find(9999999999L)).thenReturn(Optional.empty());
        when(repository.find(1200001L)).thenThrow(new DataAccessResourceFailureException("ORA-12541 detail"));
        when(repository.find(1200005L)).thenReturn(Optional.of(Map.of("STATUS_CODE", "DP")));
        Object[][] cases = {{"9999999999", 404, "policy.inquiry.notFound"},
                {"ABC123", 400, "policy.inquiry.invalidPolicyNumber"},
                {"1".repeat(31), 400, "policy.inquiry.invalidPolicyNumber"},
                {"9223372036854775808", 400, "policy.inquiry.invalidPolicyNumber"},
                {"1200001", 503, "policy.inquiry.unavailable"},
                {"1200005", 422, "policy.status.unmapped"}};
        for (Object[] c : cases) {
            String body = body("/v1/policies/" + c[0] + "/summary", "err-" + c[1], (int) c[1]);
            SchemaAssertions.assertValid("Error", body);
            assertTrue(body.contains("\"code\":\"" + c[2] + "\""), body);
            assertFalse(body.contains((String) c[0]), body);
            assertFalse(body.contains("ORA-"), body);
        }
        body("/v1/policies/9999999999/summary", null, 404);
        verify(repository, times(2)).find(9999999999L);
        verify(repository, times(4)).find(anyLong());
    }
}
