package app.synthetic.insurance;

import java.math.BigDecimal;
import java.sql.Timestamp;
import java.time.LocalDate;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.dao.DataAccessResourceFailureException;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

class InquiryTest {
    private InquiryRepository repository;
    private MockMvc mvc;

    @BeforeEach
    void setup() {
        repository = mock(InquiryRepository.class);
        mvc = MockMvcBuilders.standaloneSetup(new InquiryController(repository)).build();
    }

    private Map<String, Object> summaryRow() {
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("CONTRACT_NO", new BigDecimal("1200137"));
        row.put("STATUS_CODE", "DP");
        row.put("PRODUCT_CODE", "ANN-1");
        row.put("PRODUCT_NAME", "Flexible Growth Annuity");
        row.put("PLAN_CODE", "FLEX");
        row.put("QUALIFICATION_CODE", "NQ");
        row.put("ISSUE_STATE", "CO");
        row.put("OWNER_NAME", "Synthetic Owner 001");
        row.put("ANNUITANT_NAME", "Synthetic Annuitant 001");
        row.put("CURRENCY_CODE", "USD");
        row.put("GRX_IND", "3");
        row.put("ISSUE_DATE", Timestamp.valueOf("2020-02-29 00:00:00"));
        row.put("EFFECTIVE_DATE", java.sql.Date.valueOf("2020-03-01"));
        row.put("MATURITY_DATE", LocalDate.of(2050, 3, 1));
        return row;
    }

    @Test
    void formatters() {
        assertEquals("000000000012345", LegacyMapper.digits(new BigDecimal("123.45"), 15, 2));
        assertEquals("00000", LegacyMapper.digits(BigDecimal.ZERO, 5, 2));
        assertEquals("10000", LegacyMapper.digits(new BigDecimal("100"), 5, 2));
        assertEquals("20200229", LegacyMapper.date(LocalDate.of(2020, 2, 29)));
        assertEquals("0001200137", LegacyMapper.digits(1200137, 10, 0));
        assertEquals("4700048288", LegacyMapper.digits(4700048288L, 10, 0));
        assertThrows(IllegalArgumentException.class, () -> LegacyMapper.digits(-1, 5, 2));
        assertThrows(IllegalArgumentException.class, () -> LegacyMapper.digits(1000, 5, 2));
        assertThrows(ArithmeticException.class, () -> LegacyMapper.digits("1.001", 5, 2));
    }

    @Test
    void summaryAcceptsPaddedAndUnpaddedNumbers() throws Exception {
        when(repository.summary(1200137)).thenReturn(Optional.of(summaryRow()));
        for (String number : List.of("1200137", "0001200137")) {
            mvc.perform(get("/pinq/v1/summary/" + number)).andExpect(status().isOk())
                    .andExpect(jsonPath("$.RTN_CD").value("00"))
                    .andExpect(jsonPath("$.CNTR_NO").value("1200137"))
                    .andExpect(jsonPath("$.STAT_CD").value("DP"))
                    .andExpect(jsonPath("$.GRX_IND").value("3"))
                    .andExpect(jsonPath("$.ISS_DT").value("20200229"));
        }
        assertTrue(LegacyMapper.summary(summaryRow()).values().stream().allMatch(String.class::isInstance));
    }

    @Test
    void valuesPadsContractAndEveryAmount() throws Exception {
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("CONTRACT_NO", new BigDecimal("1200137"));
        row.put("VALUATION_DATE", java.sql.Date.valueOf("2026-06-30"));
        for (String field : List.of("ACCOUNT_VALUE", "SURRENDER_VALUE", "CASH_VALUE", "PREMIUMS_TO_DATE",
                "WITHDRAWALS_TO_DATE", "DEATH_BENEFIT", "SURRENDER_CHARGE")) {
            row.put(field, new BigDecimal("123.45"));
        }
        when(repository.values(1200137)).thenReturn(Optional.of(row));
        mvc.perform(get("/pinq/v1/values/0001200137")).andExpect(status().isOk())
                .andExpect(jsonPath("$.CNTR_NO").value("0001200137"))
                .andExpect(jsonPath("$.VAL_DT").value("20260630"));
        LegacyMapper.values(row).forEach((key, value) -> {
            if (!List.of("RTN_CD", "CNTR_NO", "VAL_DT").contains(key)) {
                assertEquals("000000000012345", value);
            }
        });
    }

    @Test
    void fundsUsesFlatNumberedGroups() throws Exception {
        Map<String, Object> row = Map.of("FUND_CODE", "FND-01", "FUND_NAME", "Balanced Growth Fund",
                "ALLOCATION_PCT", new BigDecimal("50.00"), "FUND_UNITS", new BigDecimal("12.345678"),
                "UNIT_VALUE", new BigDecimal("10.000000"), "FUND_VALUE", new BigDecimal("123.46"));
        when(repository.funds(1200137)).thenReturn(List.of(row, row));
        mvc.perform(get("/pinq/v1/funds/0001200137")).andExpect(status().isOk())
                .andExpect(jsonPath("$.CNTR_NO").value("1200137"))
                .andExpect(jsonPath("$.FUND_CNT").value("2"))
                .andExpect(jsonPath("$.ALLOC_PCT_01").value("05000"))
                .andExpect(jsonPath("$.FUND_UNITS_01").value("000000000012345678"))
                .andExpect(jsonPath("$.UNIT_VAL_01").value("000000010000000"))
                .andExpect(jsonPath("$.FUND_VAL_02").value("000000000012346"));
    }

    @Test
    void missingAndInvalidContracts() throws Exception {
        for (String operation : List.of("summary", "values", "funds")) {
            mvc.perform(get("/pinq/v1/" + operation + "/999")).andExpect(status().isNotFound())
                    .andExpect(content().json("{\"RTN_CD\":\"04\"}", true));
            mvc.perform(get("/pinq/v1/" + operation + "/abc")).andExpect(status().isBadRequest())
                    .andExpect(jsonPath("$.RTN_CD").value("08"));
        }
    }

    @Test
    void contractsIncludesEmptySet() throws Exception {
        when(repository.contracts()).thenReturn(List.of());
        mvc.perform(get("/pinq/v1/contracts")).andExpect(status().isOk())
                .andExpect(content().json("{\"RTN_CD\":\"00\",\"CNTR_CNT\":\"0\"}", true));
        when(repository.contracts()).thenReturn(List.of(1200137L, 4700048288L));
        mvc.perform(get("/pinq/v1/contracts")).andExpect(status().isOk())
                .andExpect(jsonPath("$.CNTR_NO_001").value("1200137"))
                .andExpect(jsonPath("$.CNTR_NO_002").value("4700048288"))
                .andExpect(jsonPath("$.CNTR_CNT").value("2"));
    }

    @Test
    void healthAndDatabaseFailure() throws Exception {
        mvc.perform(get("/health")).andExpect(status().isOk())
                .andExpect(content().json("{\"STATUS\":\"UP\",\"DB\":\"UP\"}", true));
        doThrow(new DataAccessResourceFailureException("Unavailable")).when(repository).ping();
        mvc.perform(get("/health")).andExpect(status().isServiceUnavailable())
                .andExpect(jsonPath("$.DB").value("DOWN"));
        when(repository.summary(1)).thenThrow(new DataAccessResourceFailureException("Unavailable"));
        mvc.perform(get("/pinq/v1/summary/1")).andExpect(status().isServiceUnavailable())
                .andExpect(jsonPath("$.RTN_CD").value("96"));
    }
}
