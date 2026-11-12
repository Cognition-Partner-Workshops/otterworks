package app.synthetic.insurance.iri.funds;

import java.math.BigDecimal;
import java.sql.Timestamp;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.dao.DataAccessResourceFailureException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.web.servlet.MockMvc;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;
import static org.hamcrest.Matchers.containsString;

@SpringBootTest(properties = "spring.autoconfigure.exclude=org.springframework.boot.autoconfigure.jdbc.DataSourceAutoConfiguration")
@AutoConfigureMockMvc
class FundsApiTest {
    private static final String FUNDS = "SELECT * FROM fund_allocation WHERE contract_no = ? ORDER BY fund_code";
    private static final String VALUES = "SELECT valuation_date FROM policy_values WHERE contract_no = ?";
    private static final BigDecimal CONTRACT = new BigDecimal("123");
    @Autowired MockMvc mvc;
    @MockBean JdbcTemplate jdbc;

    @BeforeEach void rows() {
        when(jdbc.queryForList(FUNDS, CONTRACT)).thenReturn(List.of(row("A"), row("B"), row("C")));
        when(jdbc.queryForList(VALUES, CONTRACT)).thenReturn(List.of(
                Map.of("VALUATION_DATE", Timestamp.valueOf("2025-03-04 00:00:00"))));
    }

    private Map<String, Object> row(String code) {
        return Map.of("FUND_CODE", code, "FUND_NAME", "Fund " + code,
                "UNIT_VALUE", new BigDecimal("123.456789"), "FUND_VALUE", new BigDecimal("987654321.09"),
                "FUND_UNITS", new BigDecimal("123456789.012345"));
    }

    @Test void defaultsAndDecimalOutput() throws Exception {
        mvc.perform(get("/v1/policies/123/funds")).andExpect(status().isOk())
                .andExpect(jsonPath("$.startIndex").value(0)).andExpect(jsonPath("$.itemsCount").value(3))
                .andExpect(jsonPath("$.totalItemsCount").value(3)).andExpect(jsonPath("$.funds[0].fundId").value("A"))
                .andExpect(jsonPath("$.funds[0].fundValuationDate").value("2025-03-04"))
                .andExpect(jsonPath("$.funds[0].fundAccountType").doesNotExist())
                .andExpect(jsonPath("$.funds[0].ALLOC_PCT").doesNotExist())
                .andExpect(content().string(containsString("\"fundPrice\":123.456789")))
                .andExpect(content().string(containsString("\"totalFundValue\":987654321.09")))
                .andExpect(content().string(containsString("\"numberOfUnits\":123456789.012345")));
    }

    @Test void slicingAndCounts() throws Exception {
        mvc.perform(get("/v1/policies/123/funds?startIndex=1&limit=1")).andExpect(status().isOk())
                .andExpect(jsonPath("$.startIndex").value(1)).andExpect(jsonPath("$.itemsCount").value(1))
                .andExpect(jsonPath("$.totalItemsCount").value(3)).andExpect(jsonPath("$.funds[0].fundId").value("B"));
        mvc.perform(get("/v1/policies/123/funds?startIndex=2147483647&limit=200")).andExpect(status().isOk())
                .andExpect(jsonPath("$.itemsCount").value(0)).andExpect(jsonPath("$.totalItemsCount").value(3))
                .andExpect(jsonPath("$.funds").isEmpty());
    }

    @Test void defaultLimitIsFifty() throws Exception {
        when(jdbc.queryForList(FUNDS, CONTRACT)).thenReturn(java.util.Collections.nCopies(60, row("A")));
        mvc.perform(get("/v1/policies/123/funds")).andExpect(status().isOk())
                .andExpect(jsonPath("$.itemsCount").value(50)).andExpect(jsonPath("$.totalItemsCount").value(60));
    }

    @Test void noValuesOmitsDateAndNulls() throws Exception {
        when(jdbc.queryForList(VALUES, CONTRACT)).thenReturn(List.of());
        Map<String, Object> row = new java.util.HashMap<>(row("A"));
        row.put("UNIT_VALUE", null);
        when(jdbc.queryForList(FUNDS, CONTRACT)).thenReturn(List.of(row));
        mvc.perform(get("/v1/policies/123/funds")).andExpect(status().isOk())
                .andExpect(jsonPath("$.funds[0].fundValuationDate").doesNotExist())
                .andExpect(jsonPath("$.funds[0].fundPrice").doesNotExist());
    }

    @Test void noFunds() throws Exception {
        when(jdbc.queryForList(FUNDS, CONTRACT)).thenReturn(List.of());
        mvc.perform(get("/v1/policies/123/funds")).andExpect(status().isNotFound())
                .andExpect(jsonPath("$.code").value("Inquiry.Request.NotFound"));
        verify(jdbc, never()).queryForList(VALUES, CONTRACT);
    }

    @Test void invalidInputs() throws Exception {
        for (String path : List.of("abc/funds", "-1/funds", "1.2/funds", "123/funds?startIndex=-1",
                "123/funds?limit=0", "123/funds?limit=201", "123/funds?limit=no", "123/funds?startIndex=no")) {
            mvc.perform(get("/v1/policies/" + path)).andExpect(status().isBadRequest())
                    .andExpect(jsonPath("$.code").value("Inquiry.Request.Invalid"));
        }
        verifyNoInteractions(jdbc);
    }

    @Test void databaseUnavailable() throws Exception {
        when(jdbc.queryForList(FUNDS, CONTRACT)).thenThrow(new DataAccessResourceFailureException("private"));
        mvc.perform(get("/v1/policies/123/funds")).andExpect(status().isServiceUnavailable())
                .andExpect(jsonPath("$.code").value("Inquiry.Request.Unavailable"));
    }

    @Test void valuesDatabaseUnavailable() throws Exception {
        when(jdbc.queryForList(VALUES, CONTRACT)).thenThrow(new DataAccessResourceFailureException("private"));
        mvc.perform(get("/v1/policies/123/funds")).andExpect(status().isServiceUnavailable());
    }
}
