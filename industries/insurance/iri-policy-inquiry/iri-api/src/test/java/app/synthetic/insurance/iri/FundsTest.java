package app.synthetic.insurance.iri;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.dao.DataAccessResourceFailureException;
import org.springframework.http.converter.json.MappingJackson2HttpMessageConverter;
import org.springframework.mock.web.MockHttpServletResponse;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

class FundsTest {
    private static final LocalDate VALUED = LocalDate.of(2026, 6, 30);
    private FundsRepository repository;
    private MockMvc mvc;

    @BeforeEach
    void setup() {
        repository = mock(FundsRepository.class);
        ObjectMapper json = new ObjectMapper().registerModule(new JavaTimeModule());
        json.disable(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS);
        mvc = MockMvcBuilders.standaloneSetup(new FundsController(repository, new FundsMapper("OTHER", FundsMapper.VALUATION_DATE_SOURCE)))
                .setControllerAdvice(new InquiryAdvice())
                .setMessageConverters(new MappingJackson2HttpMessageConverter(json))
                .addFilters(new CorrelationFilter()).build();
    }

    private static FundsRepository.FundRow row(String code, String name, String unit, String value, LocalDate date) {
        return new FundsRepository.FundRow(code, name, new BigDecimal(unit), new BigDecimal(value), date);
    }

    private List<FundsRepository.FundRow> twoFunds() {
        return List.of(row("FND-01", "Balanced Growth Fund", "10", "26250", VALUED),
                row("FND-02", "Stable Income Fund", "12.345678", "1234567.89", VALUED));
    }

    private MockHttpServletResponse call(String path, int status) throws Exception {
        return mvc.perform(get(path).header("correlationId", "funds-id")).andExpect(status().is(status))
                .andExpect(header().string("correlationId", "funds-id")).andReturn().getResponse();
    }

    @Test
    void mapsFundsToSchemaValidPolicyFunds() throws Exception {
        when(repository.funds(1200274L)).thenReturn(twoFunds());
        MockHttpServletResponse response = call("/v1/policies/0001200274/funds", 200);
        String body = response.getContentAsString();
        SchemaAssertions.assertValid("PolicyFunds", body);
        verify(repository).funds(1200274L);
        assertEquals("{\"startIndex\":0,\"itemsCount\":2,\"totalItemsCount\":2,\"funds\":["
                + "{\"fundAccountType\":\"OTHER\",\"fundId\":\"FND-01\",\"fundName\":\"Balanced Growth Fund\","
                + "\"fundPrice\":10.000000,\"fundValuationDate\":\"2026-06-30\",\"totalFundValue\":26250.00},"
                + "{\"fundAccountType\":\"OTHER\",\"fundId\":\"FND-02\",\"fundName\":\"Stable Income Fund\","
                + "\"fundPrice\":12.345678,\"fundValuationDate\":\"2026-06-30\",\"totalFundValue\":1234567.89}]}", body);
        assertFalse(body.contains("policyNumber"));
    }

    @Test
    void generatesCorrelationIdWhenAbsent() throws Exception {
        when(repository.funds(1200137L)).thenReturn(twoFunds());
        String generated = mvc.perform(get("/v1/policies/1200137/funds")).andExpect(status().isOk())
                .andReturn().getResponse().getHeader("correlationId");
        assertDoesNotThrow(() -> UUID.fromString(generated));
    }

    @Test
    void pagesWithinTheIriEnvelope() throws Exception {
        when(repository.funds(1200274L)).thenReturn(twoFunds());
        MockHttpServletResponse response = call("/v1/policies/1200274/funds?startIndex=1&limit=1", 200);
        SchemaAssertions.assertValid("PolicyFunds", response.getContentAsString());
        mvc.perform(get("/v1/policies/1200274/funds?startIndex=1&limit=1"))
                .andExpect(jsonPath("$.startIndex").value(1)).andExpect(jsonPath("$.itemsCount").value(1))
                .andExpect(jsonPath("$.totalItemsCount").value(2)).andExpect(jsonPath("$.funds[0].fundId").value("FND-02"));
        mvc.perform(get("/v1/policies/1200274/funds?startIndex=5"))
                .andExpect(status().isOk()).andExpect(jsonPath("$.itemsCount").value(0))
                .andExpect(jsonPath("$.totalItemsCount").value(2)).andExpect(jsonPath("$.funds").isEmpty());
    }

    @Test
    void rejectsInvalidPaging() throws Exception {
        when(repository.funds(1200274L)).thenReturn(twoFunds());
        for (String query : new String[] {"limit=0", "limit=201", "limit=abc", "startIndex=-1", "startIndex=99999999999"}) {
            MockHttpServletResponse response = call("/v1/policies/1200274/funds?" + query, 400);
            SchemaAssertions.assertValid("Error", response.getContentAsString());
            assertTrue(response.getContentAsString().contains("\"code\":\"policy.inquiry.invalidPaging\""), query);
        }
    }

    @Test
    void errorBodiesMatchSchema() throws Exception {
        when(repository.funds(9999999999L)).thenReturn(List.of());
        when(repository.funds(1200411L)).thenThrow(new DataAccessResourceFailureException("ORA-12541 detail"));
        String[] paths = {"9999999999", "ABC123", "1".repeat(31), "1200411"};
        int[] statuses = {404, 400, 400, 503};
        String[] codes = {"policy.inquiry.notFound", "policy.inquiry.invalidPolicyNumber",
                "policy.inquiry.invalidPolicyNumber", "policy.inquiry.unavailable"};
        for (int i = 0; i < paths.length; i++) {
            String body = call("/v1/policies/" + paths[i] + "/funds", statuses[i]).getContentAsString();
            SchemaAssertions.assertValid("Error", body);
            assertTrue(body.contains("\"code\":\"" + codes[i] + "\""), body);
            assertFalse(body.contains("ORA-"), body);
        }
    }

    @Test
    void signoffCasesReturnSchemaValid422() throws Exception {
        when(repository.funds(1L)).thenReturn(List.of(row("FND-01", "Fund", "10", "100", null)));
        when(repository.funds(2L)).thenReturn(List.of(row("FND-01", "Fund", "10", "10000000000.00", VALUED)));
        when(repository.funds(3L)).thenReturn(List.of(row("FND-01", "Fund", "-1", "100", VALUED)));
        String[][] cases = {{"1", "policy.funds.valuationDateMissing"}, {"2", "policy.funds.valueOutOfRange"},
                {"3", "policy.funds.valueOutOfRange"}};
        for (String[] c : cases) {
            String body = call("/v1/policies/" + c[0] + "/funds", 422).getContentAsString();
            SchemaAssertions.assertValid("Error", body);
            assertTrue(body.contains("\"code\":\"" + c[1] + "\""), body);
        }
    }

    @Test
    void impliedDecimalsAreExact() {
        assertEquals("10.000000", FundsMapper.impliedDecimal(new BigDecimal("10"), 6).toPlainString());
        assertEquals("0.000001", FundsMapper.impliedDecimal(new BigDecimal("0.000001"), 6).toPlainString());
        assertEquals("512.50", FundsMapper.impliedDecimal(new BigDecimal("512.5"), 2).toPlainString());
        assertEquals("0.00", FundsMapper.impliedDecimal(BigDecimal.ZERO, 2).toPlainString());
        assertThrows(ArithmeticException.class, () -> FundsMapper.impliedDecimal(new BigDecimal("0.001"), 2));
    }

    @Test
    void provisionalConfigIsValidated() {
        assertThrows(IllegalStateException.class, () -> new FundsMapper("MUTUAL", FundsMapper.VALUATION_DATE_SOURCE));
        assertThrows(IllegalStateException.class, () -> new FundsMapper("OTHER", "response-time"));
        assertDoesNotThrow(() -> new FundsMapper("OTHER", FundsMapper.VALUATION_DATE_SOURCE));
    }
}
