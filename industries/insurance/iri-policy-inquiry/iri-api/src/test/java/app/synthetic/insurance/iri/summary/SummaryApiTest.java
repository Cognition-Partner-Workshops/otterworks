package app.synthetic.insurance.iri.summary;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.sql.Timestamp;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.dao.DataAccessResourceFailureException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.web.servlet.MockMvc;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest(properties = {
        "spring.autoconfigure.exclude=org.springframework.boot.autoconfigure.jdbc.DataSourceAutoConfiguration",
        "IRI_CARRIER_ID=", "IRI_CARRIER_NAME="})
@AutoConfigureMockMvc
class SummaryApiTest {
    private static final String SQL = "SELECT * FROM annuity_policy WHERE contract_no = ?";
    @Autowired MockMvc mvc;
    @Autowired ObjectMapper mapper;
    @MockBean JdbcTemplate jdbc;

    private Map<String, Object> row() {
        return new HashMap<>(Map.of("STATUS_CODE", "IF", "PRODUCT_NAME", "Annuity",
                "PLAN_CODE", "FIXED", "PRODUCT_CODE", "P01", "QUALIFICATION_CODE", "NQ",
                "EFFECTIVE_DATE", Timestamp.valueOf("2020-02-29 23:45:00"),
                "ISSUE_STATE", "CA", "CURRENCY_CODE", "USD", "GRX_IND", 3));
    }

    @Test void summaryPreservesFieldsAndNullKeys() throws Exception {
        when(jdbc.queryForList(SQL, 1200137L)).thenReturn(List.of(row()));
        String body = mvc.perform(get("/v1/policies/001200137/summary?associatedFirmId=firm")
                .header("correlationId", "summary-test"))
            .andExpect(status().isOk()).andExpect(header().string("correlationId", "summary-test"))
            .andExpect(jsonPath("$.effectiveDate").value("2020-02-29"))
            .andExpect(jsonPath("$.qualificationType").value("Non-Qualified"))
            .andExpect(jsonPath("$.issueState").value("CA"))
            .andExpect(jsonPath("$.currency").value("USD"))
            .andExpect(jsonPath("$.product.planName").value("Annuity"))
            .andExpect(jsonPath("$.product.planCode").value("FIXED"))
            .andExpect(jsonPath("$.product.shortName").value("P01"))
            .andExpect(jsonPath("$.legacyUnmapped.GRX_IND").value("3"))
            .andReturn().getResponse().getContentAsString();
        JsonNode json = mapper.readTree(body);
        for (String key : List.of("carrierId", "carrierName", "issueType", "policyLastRefreshDateTime")) {
            assertTrue(json.has(key), key);
            assertTrue(json.get(key).isNull(), key);
        }
        assertTrue(json.get("product").has("productType"));
        assertTrue(json.get("product").get("productType").isNull());
        assertEquals(11, json.size());
    }

    @ParameterizedTest
    @CsvSource({"IF,ACTIVE", "LP,LAPSED", "SR,SURRENDERED", "TM,TERMINATED",
            "PI,PENDINGISSUED", "DP,DP", "ZZ,ZZ"})
    void statusMapping(String code, String expected) throws Exception {
        Map<String, Object> row = row();
        row.put("STATUS_CODE", code);
        when(jdbc.queryForList(SQL, 1L)).thenReturn(List.of(row));
        mvc.perform(get("/v1/policies/1/summary")).andExpect(status().isOk())
            .andExpect(jsonPath("$.policyStatus").value(expected));
    }

    @ParameterizedTest
    @CsvSource({"IRA,IRA", "ROTH,Roth IRA", "OTHER,OTHER"})
    void qualificationAndSqlDate(String code, String expected) throws Exception {
        Map<String, Object> row = row();
        row.put("QUALIFICATION_CODE", code);
        row.put("EFFECTIVE_DATE", java.sql.Date.valueOf("2021-01-01"));
        when(jdbc.queryForList(SQL, 1L)).thenReturn(List.of(row));
        mvc.perform(get("/v1/policies/1/summary")).andExpect(status().isOk())
            .andExpect(jsonPath("$.qualificationType").value(expected))
            .andExpect(jsonPath("$.effectiveDate").value("2021-01-01"));
    }

    @ParameterizedTest
    @CsvSource({"abc", "-1", "9223372036854775808", "1.2"})
    void invalidPolicy(String value) throws Exception {
        mvc.perform(get("/v1/policies/" + value + "/summary")).andExpect(status().isBadRequest())
            .andExpect(jsonPath("$.code").value("Inquiry.Request.Invalid"))
            .andExpect(jsonPath("$.message").isString())
            .andExpect(jsonPath("$.correlationId").doesNotExist())
            .andExpect(header().exists("correlationId"));
        verifyNoInteractions(jdbc);
    }

    @Test void missingPolicy() throws Exception {
        when(jdbc.queryForList(SQL, 1L)).thenReturn(List.of());
        mvc.perform(get("/v1/policies/1/summary")).andExpect(status().isNotFound())
            .andExpect(jsonPath("$.code").value("Inquiry.Request.NotFound"));
    }

    @Test void databaseFailure() throws Exception {
        when(jdbc.queryForList(SQL, 1L)).thenThrow(new DataAccessResourceFailureException("private details"));
        mvc.perform(get("/v1/policies/1/summary")).andExpect(status().isServiceUnavailable())
            .andExpect(jsonPath("$.code").value("Inquiry.Request.Unavailable"))
            .andExpect(jsonPath("$.message").value("Policy inquiry data unavailable"))
            .andExpect(jsonPath("$.correlationId").doesNotExist());
    }

    @Test void configuredCarrier() {
        when(jdbc.queryForList(SQL, 1L)).thenReturn(List.of(row()));
        PolicySummary summary = new SummaryController(jdbc, "C01", "Carrier").getPolicySummary("1");
        assertEquals("C01", summary.carrierId());
        assertEquals("Carrier", summary.carrierName());
    }
}
